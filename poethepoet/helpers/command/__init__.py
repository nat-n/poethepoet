from __future__ import annotations

import re
from glob import escape
from typing import TYPE_CHECKING, cast

from .ast import Comment

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from .ast import Line, ParseConfig


def parse_poe_cmd(source: str, config: ParseConfig | None = None):
    from .ast import Glob, ParseConfig, ParseCursor, PythonGlob, Script

    if not config:
        # Poe cmd task content differs from POSIX command lines in that new lines are
        # ignored (except in comments) and glob patterns are constrained to what the
        # python standard library glob module can support
        config = ParseConfig(substitute_nodes={Glob: PythonGlob}, line_separators=";")

    return Script(ParseCursor.from_string(source), config)


def resolve_command_tokens(
    lines: Iterable[Line],
    env: Mapping[str, str],
    config: ParseConfig | None = None,
) -> Iterator[tuple[str, bool]]:
    """
    Generates a sequence of tokens, and indicates for each whether it includes glob
    patterns that are not escaped or quoted. In case there are glob patterns in the
    token, any escaped glob characters will have been escaped with [].
    """
    from .ast import (
        Glob,
        ParamArgument,
        ParamExpansion,
        ParseConfig,
        PythonGlob,
        WhitespaceText,
    )

    if not config:
        config = ParseConfig(substitute_nodes={Glob: PythonGlob})

    glob_pattern = re.compile(cast("Glob", config.resolve_node_cls(Glob)).PATTERN)

    def finalize_token(token_parts):
        """
        Determine whether any parts of this token include an active glob.
        If so then apply glob escaping to all other parts.
        Join the result into a single token string.
        """
        includes_glob = any(has_glob for part, has_glob in token_parts)
        token = "".join(
            (
                (escape(token_part) if not has_glob else token_part)
                for token_part, has_glob in token_parts
            )
            if includes_glob
            else (token_part for token_part, _ in token_parts)
        )
        token_parts.clear()
        return (token, includes_glob)

    def resolve_param_argument(argument: ParamArgument, env: Mapping[str, str]):
        token_parts = []
        for segment in argument.segments:
            for element in segment:
                if isinstance(element, ParamExpansion):
                    token_parts.append(resolve_param_value(element, env))
                else:
                    token_parts.append(element.content)

        return "".join(token_parts)

    def resolve_param_value(element: ParamExpansion, env: Mapping[str, str]):
        param_value = env.get(element.param_name, "")

        if element.operation:
            if param_value:
                if element.operation.operator == ":+":
                    # apply 'alternate value' operation
                    param_value = resolve_param_argument(
                        element.operation.argument, env
                    )

            elif element.operation.operator == ":-":
                # apply 'default value' operation
                param_value = resolve_param_argument(element.operation.argument, env)

        return param_value

    def get_operation_argument(
        element: ParamExpansion, env: Mapping[str, str]
    ) -> ParamArgument | None:
        """
        If param expansion has an active :+/:- operation, return the argument
        for inline expansion (to preserve quote structure).
        """
        if not element.operation:
            return None
        param_value = env.get(element.param_name, "")
        if param_value and element.operation.operator == ":+":
            return element.operation.argument
        if not param_value and element.operation.operator == ":-":
            return element.operation.argument
        return None

    for line in lines:
        # Ignore line breaks, assuming they're only due to comments
        for word in line:
            if isinstance(word, Comment):
                # strip out comments
                continue

            token_parts: list[tuple[str, bool]] = []
            for segment in word:
                for element in segment:
                    if isinstance(element, ParamExpansion):
                        # For unquoted expansions with active operations,
                        # expand the argument inline to preserve quote
                        # structure (e.g. single-quoted strings within the
                        # operation argument stay as single tokens).
                        if not segment.is_quoted:
                            op_arg = get_operation_argument(element, env)
                            if op_arg is not None:
                                for arg_seg in op_arg.segments:
                                    for arg_el in arg_seg:
                                        if isinstance(arg_el, ParamExpansion):
                                            nested = resolve_param_value(
                                                arg_el, env
                                            )
                                            if not nested:
                                                continue
                                            if arg_seg.is_quoted:
                                                token_parts.append(
                                                    (nested, False)
                                                )
                                            elif nested.isspace():
                                                if token_parts:
                                                    yield finalize_token(
                                                        token_parts
                                                    )
                                            else:
                                                if (
                                                    nested[0].isspace()
                                                    and token_parts
                                                ):
                                                    yield finalize_token(
                                                        token_parts
                                                    )
                                                pwords = (
                                                    (
                                                        w,
                                                        bool(
                                                            glob_pattern.search(
                                                                w
                                                            )
                                                        ),
                                                    )
                                                    for w in nested.split()
                                                )
                                                token_parts.append(
                                                    next(pwords)
                                                )
                                                for pw in pwords:
                                                    if token_parts:
                                                        yield finalize_token(
                                                            token_parts
                                                        )
                                                    token_parts.append(pw)
                                                if (
                                                    nested[-1].isspace()
                                                    and token_parts
                                                ):
                                                    yield finalize_token(
                                                        token_parts
                                                    )
                                        elif (
                                            isinstance(arg_el, WhitespaceText)
                                            and not arg_seg.is_quoted
                                        ):
                                            if token_parts:
                                                yield finalize_token(
                                                    token_parts
                                                )
                                        else:
                                            token_parts.append(
                                                (arg_el.content, False)
                                            )
                                continue

                        param_value = resolve_param_value(element, env)
                        if not param_value:
                            # Empty param value has no effect
                            continue
                        if segment.is_quoted:
                            token_parts.append((param_value, False))
                        elif param_value.isspace():
                            # collapse whitespace value
                            token_parts.append((" ", False))
                        else:
                            # If the the param expansion it not quoted then:
                            # - Whitespace inside a substituted param value results in
                            #  a word break, regardless of quotes or backslashes
                            # - glob patterns should be evaluated

                            if param_value[0].isspace() and token_parts:
                                # param_value starts with a word break
                                yield finalize_token(token_parts)

                            param_words = (
                                (word, bool(glob_pattern.search(word)))
                                for word in param_value.split()
                            )

                            token_parts.append(next(param_words))

                            for param_word in param_words:
                                if token_parts:
                                    yield finalize_token(token_parts)
                                token_parts.append(param_word)

                            if param_value[-1].isspace() and token_parts:
                                # param_value ends with a word break
                                yield finalize_token(token_parts)

                    elif isinstance(element, Glob):
                        token_parts.append((element.content, True))

                    else:
                        token_parts.append((element.content, False))

            if token_parts:
                yield finalize_token(token_parts)
