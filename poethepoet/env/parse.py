from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ..helpers.command.ast import (
        EnvFileDQString,
        EnvFileValue,
        ParamArgument,
        ParamExpansion,
    )


def parse_env_file(content: str) -> dict[str, str]:
    """
    Parse an envfile string and return a dict of variable assignments.

    Semantics:
    - Values extend to end of line (bash assignment syntax)
    - ; is a regular character
    - # after whitespace is a comment; mid-word # is literal
    - Trailing whitespace stripped from unquoted suffixes
    - $VAR, ${VAR}, ${VAR:-default}, ${VAR:+alt} expanded progressively
    - Single-quoted values not expanded; double-quoted values expanded
    """
    from ..helpers.command.ast import EnvFile, ParseConfig, ParseCursor
    from ..helpers.command.ast_core import ParseError as AstParseError

    try:
        tree = EnvFile(ParseCursor.from_string(content + "\n"), ParseConfig())
        result: dict[str, str] = {}
        for assignment in tree:
            result[assignment.name] = _resolve_value(assignment.value, result)
        return result
    except AstParseError as error:
        raise ValueError(str(error)) from error


def _resolve_value(value: EnvFileValue, env: Mapping[str, str]) -> str:
    from ..helpers.command.ast import EnvFileDQString, ParamExpansion

    parts: list[str] = []
    for child in value:
        if isinstance(child, ParamExpansion):
            parts.append(_resolve_param(child, env))
        elif isinstance(child, EnvFileDQString):
            parts.append(_resolve_dq_string(child, env))
        else:
            parts.append(str(child))
    return "".join(parts)


def _resolve_dq_string(dq: EnvFileDQString, env: Mapping[str, str]) -> str:
    from ..helpers.command.ast import ParamExpansion

    parts: list[str] = []
    for child in dq:
        if isinstance(child, ParamExpansion):
            parts.append(_resolve_param(child, env))
        else:
            parts.append(str(child))
    return "".join(parts)


def _resolve_param(element: ParamExpansion, env: Mapping[str, str]) -> str:
    param_value = env.get(element.param_name, "")

    if element.operation:
        if param_value:
            if element.operation.operator == ":+":
                return _resolve_param_argument(element.operation.argument, env)
        elif element.operation.operator == ":-":
            return _resolve_param_argument(element.operation.argument, env)

    return param_value


def _resolve_param_argument(
    argument: ParamArgument,
    env: Mapping[str, str],
) -> str:
    from ..helpers.command.ast import ParamExpansion

    parts: list[str] = []
    for segment in argument.segments:
        for element in segment:
            if isinstance(element, ParamExpansion):
                parts.append(_resolve_param(element, env))
            else:
                parts.append(element.content)
    return "".join(parts)
