from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .command import ParseConfig
    from .template import Template


def parse_poe_cmd(source: str, config: ParseConfig | None = None):
    from .command import Glob, ParseConfig, ParseCursor, PythonGlob, Script

    if not config:
        # Poe cmd task content differs from POSIX command lines in that new lines are
        # ignored (except in comments) and glob patterns are constrained to what the
        # python standard library glob module can support
        config = ParseConfig(substitute_nodes={Glob: PythonGlob}, line_separators=";")

    return Script(ParseCursor.from_string(source), config)


def parse_template(source: str, require_braces: bool = False) -> Template:
    """
    Parse a template string into a Template AST node.

    The result can be resolved via Template.resolve(env), or inspected
    directly (e.g. to find ParamExpansion nodes by name).
    """
    from .command import ParseConfig, ParseCursor
    from .template import Template

    config = ParseConfig(require_braces=require_braces)
    return Template(ParseCursor.from_string(source), config)
