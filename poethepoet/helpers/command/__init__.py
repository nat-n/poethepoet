import re
from collections.abc import Iterable, Iterator, Mapping
from glob import escape
from typing import TYPE_CHECKING, Optional, cast

from .ast import Comment

if TYPE_CHECKING:
    from .ast import Line, ParseConfig


def parse_poe_cmd(source: str, config: Optional["ParseConfig"] = None):
    from .ast import Glob, ParseConfig, ParseCursor, PythonGlob, Script

    if not config:
        # Poe cmd task content differs from POSIX command lines in that new lines are
        # ignored (except in comments) and glob patterns are constrained to what the
        # python standard library glob module can support
        config = ParseConfig(substitute_nodes={Glob: PythonGlob}, line_separators=";")

    return Script(ParseCursor.from_string(source), config)


def resolve_command_tokens(
    lines: Iterable["Line"],
    env: Mapping[str, str],
    config: Optional["ParseConfig"] = None,
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
