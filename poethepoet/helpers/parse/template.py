# ruff: noqa: N806
"""
This module implements AST nodes for parsing template strings with parameter
expansion. Unlike the command parser, templates are flat strings — no word
splitting, quoting, globs, or comments, just text with `$VAR` / `${VAR:-default}`
interpolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .command import ParamExpansion
from .core import ContentNode, ParseCursor, SyntaxNode

if TYPE_CHECKING:
    from collections.abc import Mapping


class TemplateText(ContentNode):
    """
    A content node for template strings that consumes everything except `$`.

    Escaping is intentionally limited compared to bash: only `\\$` and `\\\\`
    are treated as escape sequences. Other backslash sequences like `\\n` pass
    through literally. This matches the existing regex-based template behavior.
    """

    def _parse(self, chars: ParseCursor):
        content: list[str] = []
        for char in chars:
            if char == "$":
                chars.pushback(char)
                break

            if char == "\\":
                next_char = chars.peek()
                if next_char in ("$", "\\"):
                    content.append(chars.take())
                    continue
                # Other \X sequences pass through literally
                content.append(char)
                continue

            content.append(char)

        if content:
            self._content = "".join(content)
        else:
            self._cancelled = True


class Template(SyntaxNode[ContentNode]):
    """
    A flat template parser that interleaves TemplateText and ParamExpansion
    children. Unlike Script, this does not handle line breaks, word splitting,
    quoting, globs, or comments — it treats everything as a flat string with
    only parameter expansion as special syntax.
    """

    def resolve(self, env: Mapping[str, str]) -> str:
        """
        Resolve parameter expansions in this template against the given env mapping.

        Returns a flat string with no word splitting or glob handling.
        Supports :- and :+ operators, including nested expansions.
        """
        return "".join(
            child.expand(env) if isinstance(child, ParamExpansion) else child.content
            for child in self
        )

    def _parse(self, chars: ParseCursor):
        ParamExpansionCls = self.get_child_node_cls(ParamExpansion)
        TemplateTextCls = self.get_child_node_cls(TemplateText)

        self._children = []
        while chars.peek() is not None:
            if chars.peek() == "$":
                if param_node := ParamExpansionCls(chars, self.config):
                    self._children.append(param_node)
                else:
                    # Bare $ that didn't form a valid expansion — consume as
                    # text by escaping the $ so TemplateText accepts it
                    chars.pushback("\\")
                    self._children.append(TemplateTextCls(chars, self.config))
            else:
                self._children.append(TemplateTextCls(chars, self.config))
