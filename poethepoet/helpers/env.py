import re
from typing import Mapping

_SHELL_VAR_PATTERN = re.compile(
    # Matches shell variable patterns, distinguishing escaped examples (to be ignored)
    # There may be a more direct way to doing this
    r"(?:"
    r"(?:[^\\]|^)(?:\\(?:\\{2})*)\$([\w\d_]+)|"  # $VAR preceded by an odd num of \
    r"(?:[^\\]|^)(?:\\(?:\\{2})*)\$\{([\w\d_]+)\}|"  # ${VAR} preceded by an odd num of \
    r"\$([\w\d_]+)|"  # $VAR
    r"\${([\w\d_]+)}"  # ${VAR}
    r")"
)


def resolve_envvars(content: str, env: Mapping[str, str]) -> str:
    """
    Template in ${environmental} $variables from env as if we were in a shell

    Supports escaping of the $ if preceded by an odd number of backslashes, in which
    case the backslash immediately precending the $ is removed. This is an
    intentionally very limited implementation of escaping semantics for the sake of
    usability.
    """
    cursor = 0
    resolved_parts = []
    for match in _SHELL_VAR_PATTERN.finditer(content):
        groups = match.groups()
        # the first two groups match escaped varnames so should be ignored
        var_name = groups[2] or groups[3]
        escaped_var_name = groups[0] or groups[1]
        if var_name:
            var_value = env.get(var_name)
            resolved_parts.append(content[cursor : match.start()])
            cursor = match.end()
            if var_value is not None:
                resolved_parts.append(var_value)
        elif escaped_var_name:
            # Remove the effective escape char
            resolved_parts.append(content[cursor : match.start()])
            cursor = match.end()
            matched = match.string[match.start() : match.end()]
            if matched[0] == "\\":
                resolved_parts.append(matched[1:])
            else:
                resolved_parts.append(matched[0:1] + matched[2:])
    resolved_parts.append(content[cursor:])
    return "".join(resolved_parts)
