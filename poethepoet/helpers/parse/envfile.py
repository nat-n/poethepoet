# ruff: noqa: N806
"""
This module implements AST nodes for parsing envfiles (dotenv-style files)
with bash-assignment semantics: values extend to EOL, semicolons are literal,
single/double quoting, backslash escaping, and parameter expansion.
"""

from __future__ import annotations

from .command import ParamExpansion, SingleQuotedText
from .core import ContentNode, ParseCursor, ParseError, SyntaxNode


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
