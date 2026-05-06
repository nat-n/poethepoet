# ruff: noqa: N806
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

from typing import TYPE_CHECKING, Literal, cast

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

        if self.config.require_braces and chars.peek() != "{":
            # In require_braces mode, bare $VAR is not a param expansion
            chars.pushback("$")
            self._cancelled = True
            return

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


class Line(SyntaxNode[Word | Comment]):
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
    def __init__(self, chars: ParseCursor, config: ParseConfig | None = None):
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


class EnvFileUnquotedText(ContentNode):
    """
    Reads unquoted envfile value text up to a stop character or end of input.

    Stop characters: $, ', ", newline, #. Handles backslash escaping:
    - backslash + newline: line continuation (consume both, emit nothing)
    - backslash + any other char: emit just that char (backslash dropped)

    Whitespace and semicolons are regular characters (not stop chars).
    Cancels if the very first character would cause a stop (empty result).
    """

    _STOP_CHARS = frozenset({"\n", "$", "'", '"', "#"})

    def _parse(self, chars: ParseCursor):
        content: list[str] = []
        for char in chars:
            if char == "\\":
                next_char = chars.peek()
                if next_char == "\n":
                    chars.take()  # consume the newline (continuation)
                    continue
                elif next_char is None:
                    raise ParseError("Unexpected end of input after backslash", chars)
                else:
                    content.append(chars.take())  # \X → X
                    continue
            elif char in self._STOP_CHARS:
                chars.pushback(char)
                break
            else:
                content.append(char)

        if content:
            self._content = "".join(content)
        else:
            self._cancelled = True


class EnvFileDQText(ContentNode):
    """
    Reads text inside a double-quoted envfile value segment.

    Stops at " or $ (to allow ParamExpansion to take over). Handles backslash
    escape sequences per bash double-quote rules:
    - backslash + " → "
    - backslash + \\ → \\
    - backslash + $ → $
    - backslash + ` → `
    - backslash + newline → line continuation (nothing emitted)
    - backslash + any other char → backslash kept, then char

    Empty content is valid (e.g. the text portion of an empty double-quoted
    string ""), so this node never cancels.
    """

    _DQ_SPECIAL = frozenset('"\\$`\n')

    def _parse(self, chars: ParseCursor):
        content: list[str] = []
        for char in chars:
            if char in ('"', "$"):
                chars.pushback(char)
                break
            elif char == "\\":
                next_char = chars.peek()
                if next_char in self._DQ_SPECIAL:
                    consumed = chars.take()
                    if consumed == "\n":
                        continue  # line continuation
                    content.append(consumed)
                else:
                    content.append(char)  # keep backslash
                    if next_char is not None:
                        content.append(chars.take())
            else:
                content.append(char)

        self._content = "".join(content)


class EnvFileDQString(SyntaxNode):
    """
    Parses a complete double-quoted envfile value string from opening " to
    closing ", dispatching EnvFileDQText and ParamExpansion alternately.
    """

    def _parse(self, chars: ParseCursor):
        assert chars.take() == '"'
        self._children = []

        EnvFileDQTextCls = self.get_child_node_cls(EnvFileDQText)
        ParamExpansionCls = self.get_child_node_cls(ParamExpansion)

        while True:
            next_char = chars.peek()
            if next_char is None:
                raise ParseError(
                    "Unexpected end of input with unmatched double quote", chars
                )
            elif next_char == '"':
                chars.take()
                return
            elif next_char == "$":
                if param_node := ParamExpansionCls(chars, self.config):
                    self._children.append(param_node)
                else:
                    # ParamExpansion cancelled and pushed $ back. Force
                    # EnvFileDQText to accept it by prepending a backslash
                    # escape so it reads \$ → $.
                    chars.pushback("\\")
                    text_node = EnvFileDQTextCls(chars, self.config)
                    if text_node:
                        self._children.append(text_node)
            else:
                text_node = EnvFileDQTextCls(chars, self.config)
                if text_node:
                    self._children.append(text_node)


class EnvFileValue(SyntaxNode):
    """
    Parses an envfile variable value from after '=' to end of line.

    Handles unquoted text, single-quoted strings, double-quoted strings, and
    parameter expansions. Trailing unquoted whitespace is stripped. Unquoted
    '#' preceded by whitespace (or at start) starts a comment.
    """

    def _parse(self, chars: ParseCursor):
        self._children = []

        EnvFileUnquotedTextCls = self.get_child_node_cls(EnvFileUnquotedText)
        SingleQuotedTextCls = self.get_child_node_cls(SingleQuotedText)
        EnvFileDQStringCls = self.get_child_node_cls(EnvFileDQString)
        ParamExpansionCls = self.get_child_node_cls(ParamExpansion)

        # Leading space/tab before content is invalid (bash disallows VAR= value)
        next_char = chars.peek()
        if next_char in (" ", "\t"):
            leading = []
            while chars.peek() in (" ", "\t"):
                leading.append(chars.take())
            following = chars.peek()
            if following not in ("#", "\n", None):
                raise ParseError("Space not allowed between '=' and value start", chars)
            # Space before comment or EOL: value is empty, return without error
            return

        # Track whether the last emitted character was whitespace (controls
        # whether a subsequent # starts a comment or is a literal character).
        last_was_whitespace = True  # True at start so a leading # is a comment

        while True:
            next_char = chars.peek()
            if next_char in ("\n", None):
                break

            if next_char == "#":
                if last_was_whitespace:
                    # Comment: consume to end of line
                    while chars.peek() not in ("\n", None):
                        chars.take()
                    break
                else:
                    # Mid-word hash: consume it and read any following unquoted text
                    chars.take()
                    following = EnvFileUnquotedTextCls(chars, self.config)
                    if following:
                        following._content = "#" + following._content
                        self._children.append(following)
                        last_char = following._content[-1:]
                        last_was_whitespace = last_char in (" ", "\t")
                    elif self._children and isinstance(
                        self._children[-1], EnvFileUnquotedText
                    ):
                        # # immediately before a stop char — append to last child
                        self._children[-1]._content += "#"
                        last_was_whitespace = False
                    else:
                        # No adjacent unquoted text — push back an escaped '#'
                        # so EnvFileUnquotedText reads it as a literal '#'.
                        chars.pushback("#")
                        chars.pushback("\\")
                        new_node = EnvFileUnquotedTextCls(chars, self.config)
                        self._children.append(new_node)
                        last_was_whitespace = False
                    continue

            elif next_char == "$":
                if param_node := ParamExpansionCls(chars, self.config):
                    self._children.append(param_node)
                    last_was_whitespace = False
                else:
                    # ParamExpansion cancelled, $ pushed back; read as unquoted
                    if text_node := EnvFileUnquotedTextCls(chars, self.config):
                        self._children.append(text_node)
                        last_char = text_node.content[-1:] if text_node.content else ""
                        last_was_whitespace = last_char in (" ", "\t")
                    else:
                        # bare $ at a stop position — should not happen, but
                        # consume to avoid an infinite loop
                        chars.take()
                        last_was_whitespace = False

            elif next_char == "'":
                chars.take()  # consume opening '
                text_node = SingleQuotedTextCls(chars, self.config)
                self._children.append(text_node)
                last_was_whitespace = False

            elif next_char == '"':
                dq_node = EnvFileDQStringCls(chars, self.config)
                self._children.append(dq_node)
                last_was_whitespace = False

            else:
                if text_node := EnvFileUnquotedTextCls(chars, self.config):
                    self._children.append(text_node)
                    last_char = text_node.content[-1:] if text_node.content else ""
                    last_was_whitespace = last_char in (" ", "\t")
                else:
                    # Nothing was consumed — stop to avoid infinite loop
                    break

        # Strip trailing whitespace from the last unquoted child
        if self._children and isinstance(self._children[-1], EnvFileUnquotedText):
            self._children[-1]._content = self._children[-1]._content.rstrip(" \t")
            if not self._children[-1]._content:
                self._children.pop()


class EnvAssignment(SyntaxNode):
    """
    Parses a single envfile variable assignment of the form:
        [export] IDENTIFIER=value

    Leading whitespace is skipped. The 'export' keyword is optional and must
    be followed by at least one space or tab. The identifier must immediately
    precede '=' with no intervening whitespace.
    """

    name: str

    def _parse(self, chars: ParseCursor):
        self._children = []
        EnvFileValueCls = self.get_child_node_cls(EnvFileValue)

        # Skip leading whitespace (indentation)
        while chars.peek() in (" ", "\t"):
            chars.take()

        # Optional 'export' keyword: read char-by-char, push back if not matched
        if chars.peek() == "e":
            saved: list[str] = []
            for expected in "export":
                ch = chars.peek()
                if ch != expected:
                    chars.pushback(*reversed(saved))
                    break
                saved.append(chars.take())
            else:
                # 'export' fully matched — require whitespace after it
                if chars.peek() not in (" ", "\t"):
                    raise ParseError("Expected whitespace after 'export'", chars)
                while chars.peek() in (" ", "\t"):
                    chars.take()

        # Read identifier: [a-zA-Z_][a-zA-Z_0-9]*
        name_chars: list[str] = []
        first = chars.peek()
        if first is None or not (first.isalpha() or first == "_"):
            raise ParseError("Expected variable name", chars)
        name_chars.append(chars.take())
        while chars.peek() is not None and (
            chars.peek().isalnum() or chars.peek() == "_"
        ):
            name_chars.append(chars.take())
        self.name = "".join(name_chars)

        # Require '=' immediately (no whitespace before it)
        if chars.peek() != "=":
            raise ParseError(f"Expected '=' after variable name {self.name!r}", chars)
        chars.take()

        # Parse value
        value_node = EnvFileValueCls(chars, self.config)
        self._children.append(value_node)

    @property
    def value(self) -> EnvFileValue:
        return self._children[0]  # type: ignore[return-value]


class EnvFile(SyntaxNode):
    """
    Root node for an envfile — parses the entire content as a sequence of
    variable assignments, skipping blank lines and comment-only lines.
    """

    def _parse(self, chars: ParseCursor):
        self._children = []
        EnvAssignmentCls = self.get_child_node_cls(EnvAssignment)

        while chars.peek() is not None:
            # Skip blank lines and carriage returns
            while chars.peek() in ("\n", "\r"):
                chars.take()
            if chars.peek() is None:
                break

            # Consume leading whitespace on this line
            line_start: list[str] = []
            while chars.peek() in (" ", "\t"):
                line_start.append(chars.take())

            if chars.peek() == "#":
                # Comment line: skip to end of line
                while chars.peek() not in ("\n", None):
                    chars.take()
                continue

            if chars.peek() in ("\n", None):
                # Blank line (only whitespace)
                continue

            # Push leading whitespace back so EnvAssignment can skip it
            chars.pushback(*reversed(line_start))

            assignment = EnvAssignmentCls(chars, self.config)
            if assignment:
                self._children.append(assignment)

            # Consume the line terminator
            if chars.peek() == "\n":
                chars.take()
