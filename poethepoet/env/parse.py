from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

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
    from ..helpers.parse.core import ParseConfig, ParseCursor
    from ..helpers.parse.core import ParseError as AstParseError
    from ..helpers.parse.envfile import EnvFile

    try:
        return EnvFile(ParseCursor.from_string(content + "\n"), ParseConfig())
    except AstParseError as error:
        raise ValueError(str(error)) from error


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
