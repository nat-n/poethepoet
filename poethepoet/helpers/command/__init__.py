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
    from .ast import Glob, ParamArgument, ParamExpansion, ParseConfig, PythonGlob

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

    def resolve_param_argument(
        argument: ParamArgument, env: Mapping[str, str]
    ) -> list[tuple[str, bool]]:
        """
        Resolve a parameter argument to a list of (text, is_quoted) tuples,
        preserving quoting information from the argument's segments so that
        quoted parts are not subject to word splitting.
        """
        parts: list[tuple[str, bool]] = []
        for segment in argument.segments:
            segment_text_parts: list[str] = []
            for element in segment:
                if isinstance(element, ParamExpansion):
                    result = resolve_param_value(element, env)
                    if isinstance(result, list):
                        # Nested operation result — flatten to string within
                        # this segment
                        segment_text_parts.append(
                            "".join(text for text, _ in result)
                        )
                    else:
                        segment_text_parts.append(result)
                else:
                    segment_text_parts.append(element.content)
            parts.append(("".join(segment_text_parts), segment.is_quoted))
        return parts

    def resolve_param_value(
        element: ParamExpansion, env: Mapping[str, str]
    ) -> str | list[tuple[str, bool]]:
        param_value = env.get(element.param_name, "")

        if element.operation:
            if param_value:
                if element.operation.operator == ":+":
                    # apply 'alternate value' operation
                    return resolve_param_argument(
                        element.operation.argument, env
                    )

            elif element.operation.operator == ":-":
                # apply 'default value' operation
                return resolve_param_argument(element.operation.argument, env)

        return param_value

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
                        param_result = resolve_param_value(element, env)

                        if isinstance(param_result, list):
                            # Structured result from :+ or :- operation
                            if not any(text for text, _ in param_result):
                                # All parts empty — no effect
                                continue

                            if segment.is_quoted:
                                # Outer context is quoted — no word splitting
                                full_text = "".join(
                                    text for text, _ in param_result
                                )
                                token_parts.append((full_text, False))
                            else:
                                for part_text, part_is_quoted in param_result:
                                    if not part_text:
                                        continue
                                    if part_is_quoted:
                                        # Quoted part: no word splitting
                                        token_parts.append(
                                            (part_text, False)
                                        )
                                    elif part_text.isspace():
                                        # Whitespace-only unquoted part
                                        if token_parts:
                                            yield finalize_token(token_parts)
                                    else:
                                        # Unquoted: apply word splitting
                                        if (
                                            part_text[0].isspace()
                                            and token_parts
                                        ):
                                            yield finalize_token(token_parts)

                                        param_words = (
                                            (
                                                pw,
                                                bool(glob_pattern.search(pw)),
                                            )
                                            for pw in part_text.split()
                                        )

                                        token_parts.append(next(param_words))

                                        for param_word in param_words:
                                            if token_parts:
                                                yield finalize_token(
                                                    token_parts
                                                )
                                            token_parts.append(param_word)

                                        if (
                                            part_text[-1].isspace()
                                            and token_parts
                                        ):
                                            yield finalize_token(token_parts)

                        else:
                            # Simple string result (no operation applied)
                            param_value = param_result
                            if not param_value:
                                # Empty param value has no effect
                                continue
                            if segment.is_quoted:
                                token_parts.append((param_value, False))
                            elif param_value.isspace():
                                # collapse whitespace value
                                token_parts.append((" ", False))
                            else:
                                # If the param expansion is not quoted then:
                                # - Whitespace inside a substituted param
                                #   value results in a word break
                                # - glob patterns should be evaluated

                                if param_value[0].isspace() and token_parts:
                                    # param_value starts with a word break
                                    yield finalize_token(token_parts)

                                param_words = (
                                    (
                                        pw,
                                        bool(glob_pattern.search(pw)),
                                    )
                                    for pw in param_value.split()
                                )

                                token_parts.append(next(param_words))

                                for param_word in param_words:
                                    if token_parts:
                                        yield finalize_token(token_parts)
                                    token_parts.append(param_word)

                                if (
                                    param_value[-1].isspace() and token_parts
                                ):
                                    # param_value ends with a word break
                                    yield finalize_token(token_parts)

                    elif isinstance(element, Glob):
                        token_parts.append((element.content, True))

                    else:
                        token_parts.append((element.content, False))

            if token_parts:
                yield finalize_token(token_parts)
