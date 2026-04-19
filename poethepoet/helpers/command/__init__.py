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
        """
        Flatten a ParamArgument to a string, discarding quote structure.
        Used when the result will be placed in an already-quoted context.
        """
        parts: list[str] = []
        for segment in argument.segments:
            for element in segment:
                if isinstance(element, ParamExpansion):
                    result = resolve_param_value(element, env)
                    if isinstance(result, ParamArgument):
                        parts.append(resolve_param_argument(result, env))
                    else:
                        parts.append(result)
                else:
                    parts.append(element.content)

        return "".join(parts)

    def resolve_param_value(
        element: ParamExpansion, env: Mapping[str, str]
    ) -> str | ParamArgument:
        """
        Returns a plain string for simple variable values, or a ParamArgument
        when an operation's argument should be processed with its quoting intact.
        """
        param_value = env.get(element.param_name, "")

        if element.operation:
            if param_value:
                if element.operation.operator == ":+":
                    return element.operation.argument
            elif element.operation.operator == ":-":
                return element.operation.argument

        return param_value

    def resolve_argument_tokens(
        argument: ParamArgument,
        env: Mapping[str, str],
        token_parts: list[tuple[str, bool]],
    ) -> Iterator[tuple[str, bool]]:
        """
        Process a ParamArgument's segments inline, respecting quoting.
        Quoted segments are not word-split; unquoted WhitespaceText causes
        word breaks.
        """
        for arg_segment in argument.segments:
            if arg_segment.is_quoted:
                for element in arg_segment:
                    if isinstance(element, ParamExpansion):
                        result = resolve_param_value(element, env)
                        if isinstance(result, ParamArgument):
                            flat = resolve_param_argument(result, env)
                            if flat:
                                token_parts.append((flat, False))
                        elif result:
                            token_parts.append((result, False))
                    else:
                        token_parts.append((element.content, False))
            else:
                for element in arg_segment:
                    if isinstance(element, WhitespaceText):
                        if token_parts:
                            yield finalize_token(token_parts)
                    elif isinstance(element, ParamExpansion):
                        result = resolve_param_value(element, env)
                        if isinstance(result, ParamArgument):
                            yield from resolve_argument_tokens(result, env, token_parts)
                        elif result:
                            yield from _emit_unquoted_param_value(result, token_parts)
                    else:
                        token_parts.append((element.content, False))

    def _emit_unquoted_param_value(
        param_value: str,
        token_parts: list[tuple[str, bool]],
    ) -> Iterator[tuple[str, bool]]:
        """
        Handle an unquoted plain string param value: word-split on whitespace
        and check for glob patterns.
        """
        if param_value.isspace():
            if token_parts:
                yield finalize_token(token_parts)
            return

        if param_value[0].isspace() and token_parts:
            yield finalize_token(token_parts)

        param_words = (
            (word, bool(glob_pattern.search(word))) for word in param_value.split()
        )

        token_parts.append(next(param_words))

        for param_word in param_words:
            if token_parts:
                yield finalize_token(token_parts)
            token_parts.append(param_word)

        if param_value[-1].isspace() and token_parts:
            yield finalize_token(token_parts)

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
                        result = resolve_param_value(element, env)

                        if isinstance(result, ParamArgument) and not segment.is_quoted:
                            # In unquoted context, process argument
                            # segments inline to preserve quoting
                            yield from resolve_argument_tokens(result, env, token_parts)
                            continue

                        # Flatten ParamArgument to string for quoted
                        # contexts (or use the string value directly)
                        param_value = (
                            resolve_param_argument(result, env)
                            if isinstance(result, ParamArgument)
                            else result
                        )
                        if not param_value:
                            continue
                        if segment.is_quoted:
                            token_parts.append((param_value, False))
                        else:
                            yield from _emit_unquoted_param_value(
                                param_value, token_parts
                            )

                    elif isinstance(element, Glob):
                        token_parts.append((element.content, True))

                    else:
                        token_parts.append((element.content, False))

            if token_parts:
                yield finalize_token(token_parts)
