# ruff: noqa: N806, UP007
r"""
This module implements a hierarchical parser and AST for a subset of bash syntax
including:

- line breaks and comments
- single or double quotes and character escaping
- basic glob patterns (python style glob patterns also supported)
- basic parameter expansion
- parameter expansion operators: `:+` and `:-`
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Union, cast

from .ast_core import (
    AnnotatedContentNode,
    ContentNode,
    ParseConfig,
    ParseCursor,
    ParseError,
    SyntaxNode,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


PARAM_INIT_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_"
PARAM_CHARS = PARAM_INIT_CHARS + "0123456789"
LINE_BREAK_CHARS = "\r\n\f\v"
LINE_SEP_CHARS = LINE_BREAK_CHARS + ";"


class SingleQuotedText(ContentNode):
    def _parse(self, chars: ParseCursor):
        content: list[str] = []
        for char in chars:
            if char == "'":
                self._content = "".join(content)
                return
            content.append(char)
        else:
            raise ParseError(
                "Unexpected end of input with unmatched single quote", chars
            )


class DoubleQuotedText(ContentNode):
    def _parse(self, chars: ParseCursor):
        content: list[str] = []
        for char in chars:
            if char == "\\":
                # backslash is only special if escape is necessary
                if chars.peek() in '"$':
                    content.append(chars.take())
                    continue

            elif char in '"$':
                chars.pushback(char)
                break

            content.append(char)

        self._content = "".join(content)


class UnquotedText(ContentNode):
    _break_chars = "'\";#$?*["

    def _parse(self, chars: ParseCursor):
        content: list[str] = []
        for char in chars:
            if char == "\\":
                # Backslash is always an escape when outside of quotes
                escaped_char = chars.take()
                if not escaped_char:
                    raise ParseError(
                        "Unexpected end of input after backslash",
                        chars,
                    )
                content.append(escaped_char)
                continue

            elif char.isspace() or char in self._break_chars:
                chars.pushback(char)
                break

            content.append(char)

        if content:
            self._content = "".join(content)
        else:
            # This should not happen
            self._cancelled = True


class Glob(ContentNode):
    """
    This implementation recognises a subset of bash style glob patterns.
    """

    # This pattern is equivalent to what this node might parse
    PATTERN = (
        r"(?P<simple>[\?\*])"
        r"|(?P<complex>\[(?:\!?\](?:[^\s\]\\]|\\.)*|(?:[^\s\]\\]|\\.)+)\])"
    )

    def _parse(self, chars: ParseCursor):
        char = chars.peek()
        if char in "*?":
            self._content = chars.take()
            return

        if char == "[":
            # Match pattern [groups]
            group_chars = []
            chars.take()
            for char in chars:
                if char.isspace():
                    # GOTO invalid group pattern
                    group_chars.append(char)
                    break

                elif char == "]":
                    if group_chars and group_chars != ["!"]:
                        # Group complete
                        self._content = f"[{''.join(group_chars)}]"
                        return
                    else:
                        # ] at start of group is interpreted as content
                        group_chars.append(char)

                elif char == "\\":
                    # Backslash is always an escape when inside a group pattern
                    escaped_char = chars.take()
                    if not escaped_char:
                        raise ParseError(
                            "Invalid pattern: unexpected end of input after backslash",
                            chars,
                        )
                    group_chars.append(escaped_char)

                else:
                    group_chars.append(char)

            # invalid group pattern, pretend it never happened
            chars.pushback("[", *group_chars)
            self._cancelled = True
            return

        else:
            # This should not happen
            # ruff: noqa: B011
            assert False
            self._cancelled = True


class PythonGlob(Glob):
    """
    This implementation recognises glob patterns supports by the python standard library
    glob module.

    The key divergences from bash style pattern matching are that within square bracket
    patterns:
        1. unescaped spaces are allowed
        2. backslashes are not interpreted as escapes
    """

    # This pattern is equivalent to what this node might parse
    PATTERN = r"(?P<simple>[\?\*])|(?P<complex>\[\!?\]?[^\]]*\])"

    def _parse(self, chars: ParseCursor):
        char = chars.peek()
        if char in "*?":
            self._content = chars.take()
            return

        if char == "[":
            # Match pattern [groups]
            group_chars: list[str] = []
            chars.take()
            for char in chars:
                if char == "]":
                    if group_chars and group_chars != ["!"]:
                        # Group complete
                        self._content = f"[{''.join(group_chars)}]"
                        return
                    else:
                        # ] at start of group is interpreted as content
                        group_chars.append(char)

                else:
                    group_chars.append(char)

            # invalid group pattern, pretend it never happened
            chars.pushback("[", *group_chars)
            self._cancelled = True
            return

        else:
            # This should not happen
            # ruff: noqa: B011
            assert False
            self._cancelled = True


class ParamExpansion(AnnotatedContentNode["ParamOperation"]):
    @property
    def param_name(self) -> str:
        return self._content

    @property
    def operation(self) -> ParamOperation | None:
        return self._annotation

    def _parse(self, chars: ParseCursor):
        assert chars.take() == "$"

        param: list[str] = []
        if chars.peek() == "{":
            chars.take()
            for char in chars:
                if char == "}":
                    if not param:
                        raise ParseError("Bad substitution: ${}", chars)

                    self._content = "".join(param)
                    return

                if param:
                    if char == ":":
                        ParamOperationCls: type = self.get_child_node_cls(
                            ParamOperation
                        )
                        chars.pushback(char)
                        self._annotation = ParamOperationCls(chars, self.config)
                        continue

                    if char not in PARAM_CHARS:
                        raise ParseError(
                            "Bad substitution: Illegal character in parameter name "
                            f"{char!r}",
                            chars,
                        )

                    param.append(char)

                elif char in PARAM_INIT_CHARS:
                    param.append(char)

                else:
                    raise ParseError(
                        "Bad substitution: Illegal first character in parameter name "
                        f"{char!r}",
                        chars,
                    )
            raise ParseError(
                "Unexpected end of input, expected closing '}' after '${'", chars
            )

        elif chars.peek() is None:
            # End of input means no param expansion
            chars.pushback("$")
            self._cancelled = True

        else:
            for char in chars:
                if param:
                    if char in PARAM_CHARS:
                        param.append(char)
                    else:
                        chars.pushback(char)
                        break
                elif char in PARAM_INIT_CHARS:
                    param.append(char)
                else:
                    # No param expansion
                    chars.pushback("$", char)
                    self._cancelled = True
                    return

            self._content = "".join(param)


class Comment(ContentNode):
    @property
    def comment(self) -> str:
        return self._content

    def _parse(self, chars: ParseCursor):
        comment = []
        for char in chars:
            if char in LINE_BREAK_CHARS:
                break
            comment.append(char)
        self._content = "".join(comment)


class Segment(SyntaxNode[ContentNode]):
    _quote_char: Literal['"', "'"] | None

    @property
    def is_quoted(self) -> bool:
        return bool(self._quote_char)

    @property
    def is_single_quoted(self) -> bool:
        return self._quote_char == "'"

    @property
    def is_double_quoted(self) -> bool:
        return self._quote_char == '"'

    def _parse(self, chars: ParseCursor):
        self._quote_char = next(chars) if chars.peek() in "'\"" else None
        self._children = []

        if self._quote_char == "'":
            return self._consume_single_quoted(chars)
        elif self._quote_char == '"':
            return self._consume_double_quoted(chars)
        else:
            return self._consume_unquoted(chars)

    def _consume_single_quoted(self, chars):
        SingleQuotedTextCls = self.get_child_node_cls(SingleQuotedText)
        self._children.append(SingleQuotedTextCls(chars, self.config))

    def _consume_double_quoted(self, chars):
        DoubleQuotedTextCls = self.get_child_node_cls(DoubleQuotedText)
        ParamExpansionCls = self.get_child_node_cls(ParamExpansion)

        while next_char := chars.peek():
            if next_char == '"':
                if not self._children:
                    # make sure this segment contains at least an empty string
                    self._children.append(DoubleQuotedTextCls(chars, self.config))
                chars.take()
                return

            elif next_char == "$":
                if param_node := ParamExpansionCls(chars, self.config):
                    self._children.append(param_node)
                else:
                    # Hack: escape the $ to make it acceptable as unquoted text
                    chars.pushback("\\")
                    self._children.append(DoubleQuotedTextCls(chars, self.config))

            else:
                self._children.append(DoubleQuotedTextCls(chars, self.config))

        raise ParseError("Unexpected end of input with unmatched double quote", chars)

    def _consume_unquoted(self, chars):
        UnquotedTextCls = self.get_child_node_cls(UnquotedText)
        GlobCls = self.get_child_node_cls(Glob)
        ParamExpansionCls = self.get_child_node_cls(ParamExpansion)

        while next_char := chars.peek():
            if next_char.isspace() or next_char in "'\";#":
                return

            elif next_char == "$":
                if param_node := ParamExpansionCls(chars, self.config):
                    self._children.append(param_node)
                else:
                    # Hack: escape the $ to make it acceptable as unquoted text
                    chars.pushback("\\")
                    self._children.append(UnquotedTextCls(chars, self.config))

            elif next_char in "*?[":
                if glob_node := GlobCls(chars, self.config):
                    self._children.append(glob_node)
                else:
                    # Hack: escape the char to make it acceptable as unquoted text
                    chars.pushback("\\")
                    self._children.append(UnquotedTextCls(chars, self.config))

            else:
                self._children.append(UnquotedTextCls(chars, self.config))


class WhitespaceText(ContentNode):
    """
    Capture unquoted whitespace strings as a single space
    """

    def _parse(self, chars: ParseCursor):
        if chars.peek().isspace():
            self._content = " "

        while char := chars.take():
            if not char.isspace():
                chars.pushback(char)
                break


class ParamArgumentUnquotedText(UnquotedText):
    """
    Just like UnquotedText except that it may include chars in `;#`, but not `}`
    """

    _break_chars = "'\"$}"


class ParamArgumentSegment(Segment):
    """
    Just like Segment except that :
    - it may include unquoted whitespace or chars in `;#`, but not `}`
    - glob characters `*?[` are not recognised as special
    """

    def _consume_unquoted(self, chars):
        UnquotedTextCls = self.get_child_node_cls(ParamArgumentUnquotedText)
        ParamExpansionCls = self.get_child_node_cls(ParamExpansion)
        WhitespaceTextCls = self.get_child_node_cls(WhitespaceText)

        while next_char := chars.peek():
            if next_char in "'\"}":
                return

            elif next_char.isspace():
                self._children.append(WhitespaceTextCls(chars, self.config))

            elif next_char == "$":
                if param_node := ParamExpansionCls(chars, self.config):
                    self._children.append(param_node)
                else:
                    # Hack: escape the $ to make it acceptable as unquoted text
                    chars.pushback("\\")
                    self._children.append(UnquotedTextCls(chars, self.config))

            else:
                self._children.append(UnquotedTextCls(chars, self.config))


class ParamArgument(SyntaxNode[ParamArgumentSegment]):
    @property
    def segments(self) -> tuple[ParamArgumentSegment, ...]:
        return tuple(self._children)

    def _parse(self, chars: ParseCursor):
        SegmentCls = self.get_child_node_cls(ParamArgumentSegment)

        self._children = []

        while next_char := chars.peek():
            if next_char == "}":
                return
            self._children.append(SegmentCls(chars, self.config))


class ParamOperation(AnnotatedContentNode[ParamArgument]):
    _content: Literal[":-", ":+"]

    @property
    def operator(self) -> Literal[":-", ":+"]:
        return self._content

    @property
    def argument(self) -> ParamArgument:
        assert self._annotation
        return self._annotation

    def _parse(self, chars: ParseCursor):
        ParamArgumentCls = self.get_child_node_cls(ParamArgument)

        op_chars = (chars.take(), chars.take())
        if None in op_chars:
            raise ParseError(
                "Unexpected end of input in param expansion, expected '}'",
                chars,
            )

        self._content = op_chars[0] + op_chars[1]
        if self._content not in (":-", ":+"):
            raise ParseError(
                f"Bad substitution: Unsupported operator {self._content!r}",
                chars,
            )

        self._annotation = ParamArgumentCls(chars, self.config)


class Word(SyntaxNode[Segment]):
    @property
    def segments(self) -> tuple[Segment, ...]:
        return tuple(self._children)

    def _parse(self, chars: ParseCursor):
        SegmentCls = self.get_child_node_cls(Segment)

        self._children = []

        while next_char := chars.peek():
            if next_char.isspace() or next_char in ";#":
                if not self._children:
                    # This should never happen
                    self._cancelled = True
                return

            self._children.append(SegmentCls(chars, self.config))


class Line(SyntaxNode[Union[Word, Comment]]):
    _terminator: str

    @property
    def words(self) -> tuple[Word, ...]:
        if self._children and isinstance(self._children[-1], Comment):
            return tuple(cast("Iterable[Word]", self._children[:-1]))
        return tuple(cast("Iterable[Word]", self._children))

    @property
    def comment(self) -> str:
        if self._children and isinstance(self._children[-1], Comment):
            return self._children[-1].comment
        return ""

    @property
    def terminator(self):
        return self._terminator

    def _parse(self, chars: ParseCursor):
        WordCls = self.get_child_node_cls(Word)
        CommentCls = self.get_child_node_cls(Comment)

        self._children = []
        for char in chars:
            if char in self.config.line_separators:
                self._terminator = char
                break

            elif char.isspace():
                continue

            elif char == "#":
                self._children.append(CommentCls(chars, self.config))
                self._terminator = char
                return

            else:
                chars.pushback(char)
                if word := WordCls(chars, self.config):
                    self._children.append(word)

        if not self._children:
            self._cancelled = True


class Script(SyntaxNode[Line]):
    def __init__(self, chars: ParseCursor, config: Union[ParseConfig, None] = None):
        config = config or ParseConfig()
        if not config.line_separators:
            config.line_separators = LINE_SEP_CHARS
        super().__init__(chars, config)

    @property
    def lines(self):
        return tuple(self._children)

    @property
    def command_lines(self):
        """
        Return just lines that have words
        """
        return tuple(line for line in self._children if line.words)

    def _parse(self, chars: ParseCursor):
        LineCls = self.get_child_node_cls(Line)

        self._children = []
        while next_char := chars.peek():
            if next_char in self.config.line_separators:
                chars.take()
                continue

            if line_node := LineCls(chars, self.config):
                self._children.append(line_node)
