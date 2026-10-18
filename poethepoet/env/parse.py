from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ..helpers.parse.core import ParseError
    from ..helpers.parse.envfile import EnvFile, EnvFileDQString, EnvFileValue


def parse_env_file(
    content: str, base_env: Mapping[str, str] | None = None
) -> dict[str, str]:
    """
    Parse an envfile string and return a dict of variable assignments.

    Semantics:
    - Values extend to end of line (bash assignment syntax)
    - ; is a regular character
    - # after whitespace is a comment; mid-word # is literal
    - Trailing whitespace stripped from unquoted suffixes
    - $VAR, ${VAR}, ${VAR:-default}, ${VAR:+alt} expanded progressively
    - Single-quoted values not expanded; double-quoted values expanded
    - base_env vars are visible during expansion; in-file definitions take precedence
    """
    return _resolve_ast(_parse_to_ast(content), base_env or {})


def _parse_to_ast(content: str) -> EnvFile:
    from ..helpers.parse.command import ParamExpansion, WhitespaceText
    from ..helpers.parse.core import ParseConfig, ParseCursor
    from ..helpers.parse.core import ParseError as AstParseError
    from ..helpers.parse.envfile import (
        EnvFile,
        EnvFileParamExpansion,
        EnvFileWhitespaceText,
    )

    # Ignore a leading UTF-8 byte order mark, as written by some Windows editors
    content = content.removeprefix("\ufeff")
    content, continuations = _join_line_continuations(content)
    if not content.endswith("\n"):
        # Terminate the last line, without adding a line that error positions count
        content += "\n"
    # Use the envfile flavours of these nodes everywhere, including in the argument of
    # ${VAR:-...}, so special parameters like $$ and runs of whitespace are kept as
    # written there too
    config = ParseConfig(
        substitute_nodes={
            ParamExpansion: EnvFileParamExpansion,
            WhitespaceText: EnvFileWhitespaceText,
        }
    )
    try:
        return EnvFile(ParseCursor.from_string(content), config)
    except AstParseError as error:
        message = error.message
        if error.has_position:
            _unjoin_position(error, continuations)
            message += f" (near {error.location})"
        raise ValueError(message) from error


def _join_line_continuations(content: str) -> tuple[str, list[tuple[int, int]]]:
    """
    Remove backslash-newline line continuations, as bash does before interpreting
    anything else, except in single quotes and comments where they are literal.

    Also returns the (line, position) in the result at which each continuation was
    removed, so that error positions can be mapped back to the original content.
    """
    result: list[str] = []
    continuations: list[tuple[int, int]] = []
    line = position = 0
    quote = None  # The quote char of the quoted string we're in, if any
    in_comment = False
    in_value = False  # Whether we've passed the = of this line's assignment
    word_start = True  # Whether a # here would start a comment

    def emit(*chars: str):
        nonlocal line, position
        for char in chars:
            result.append(char)
            if char == "\n":
                line += 1
                position = 0
            else:
                position += 1

    index = 0
    while index < len(content):
        char = content[index]
        next_char = content[index + 1] if index + 1 < len(content) else None
        index += 1

        if in_comment and char != "\n":
            emit(char)
            continue

        if char == "\\" and quote != "'":
            if next_char == "\n":
                continuations.append((line, position))
                index += 1
            elif next_char is not None and (quote is None or next_char in '"\\$`'):
                # An escaped char, which mustn't start a continuation itself
                emit(char, next_char)
                index += 1
                word_start = False
            else:
                emit(char)
                word_start = False
            continue

        emit(char)
        if quote:
            if char == quote:
                quote = None
        elif char == "\n":
            in_comment = in_value = False
            word_start = True
        elif char in "'\"":
            quote = char
            word_start = False
        elif char == "#" and word_start:
            in_comment = True
        elif char in " \t":
            word_start = True
        elif char == "=" and not in_value:
            in_value = word_start = True
        else:
            word_start = False

    return "".join(result), continuations


def _unjoin_position(error: ParseError, continuations: list[tuple[int, int]]):
    """
    Map the position of a parse error in content with line continuations removed back
    to the position in the original content.
    """
    if error.line is None or error.position is None:
        return
    line, position = error.line, error.position
    for removed_line, removed_position in continuations:
        if removed_line < error.line or (
            removed_line == error.line and removed_position <= error.position
        ):
            line += 1
            if removed_line == error.line:
                position = error.position - removed_position
    error.line, error.position = line, position


def _resolve_ast(tree: EnvFile, base_env: Mapping[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for assignment in tree:
        env = {**base_env, **result}
        result[assignment.name] = _resolve_value(assignment.value, env)
    return result


def _resolve_value(value: EnvFileValue, env: Mapping[str, str]) -> str:
    from ..helpers.parse.command import ParamExpansion
    from ..helpers.parse.envfile import EnvFileDQString

    parts: list[str] = []
    for child in value:
        if isinstance(child, ParamExpansion):
            parts.append(child.expand(env))
        elif isinstance(child, EnvFileDQString):
            parts.append(_resolve_dq_string(child, env))
        else:
            parts.append(str(child))
    return "".join(parts)


def _resolve_dq_string(dq: EnvFileDQString, env: Mapping[str, str]) -> str:
    from ..helpers.parse.command import ParamExpansion

    return "".join(
        child.expand(env) if isinstance(child, ParamExpansion) else str(child)
        for child in dq
    )
