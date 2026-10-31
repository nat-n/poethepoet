# ruff: noqa: N806
r"""
This module implements a hierarchical parser and AST for a subset of bash syntax
including:

- line breaks and comments
- single or double quotes and character escaping
- basic glob patterns
- basic parameter expansion
- parameter expansion operators: `:+` and `:-`
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

from .core import (
    AnnotatedContentNode,
    ContentNode,
    ParseConfig,
    ParseCursor,
    ParseError,
    SyntaxNode,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping


PARAM_INIT_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_"
PARAM_CHARS = PARAM_INIT_CHARS + "0123456789"
LINE_BREAK_CHARS = "\r\n\f\v"
LINE_SEP_CHARS = LINE_BREAK_CHARS + ";"
GLOB_CHARS = "*?["

# How glob syntax applies to one part of a resolved token
QUOTED = 0  # nothing is special
UNQUOTED = 1  # only the syntax within a bracket pattern is special: `]`, `!`, `-`
PATTERN = 2  # everything is special, including `*`, `?`, and `[`


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
    _parts: tuple[tuple[str, int], ...] = ()

    @property
    def parts(self) -> tuple[tuple[str, int], ...]:
        """
        The content of this node as (text, kind) pairs, which differs from simply
        being UNQUOTED if it includes backslash escaped chars.
        """
        return self._parts or ((self._content, UNQUOTED),)

    def _parse(self, chars: ParseCursor):
        content: list[str] = []
        escaped_indexes: set[int] = set()
        for char in chars:
            if char == "\\":
                # Backslash is always an escape when outside of quotes
                escaped_char = chars.take()
                if not escaped_char:
                    raise ParseError(
                        "Unexpected end of input after backslash",
                        chars,
                    )
                escaped_indexes.add(len(content))
                content.append(escaped_char)
                continue

            if char.isspace() or char in self._break_chars:
                chars.pushback(char)
                break

            content.append(char)

        if content:
            self._content = "".join(content)
            if escaped_indexes:
                self._parts = tuple(
                    (char, QUOTED if index in escaped_indexes else UNQUOTED)
                    for index, char in enumerate(content)
                )
        else:
            # This should not happen
            self._cancelled = True


class Glob(ContentNode):
    """
    This implementation recognises a subset of bash style glob patterns, limited to
    what can be translated for the python standard library glob module.

    A group pattern that includes a quote or a parameter expansion cannot be
    captured as a single node. In that case only the opening bracket is captured,
    the rest of the group is left to be parsed as part of the word, and whether the
    bracket really opens a group is determined when the word is resolved.
    """

    _parts: tuple[tuple[str, int], ...] = ()

    @property
    def parts(self) -> tuple[tuple[str, int], ...]:
        """
        The content of this node as (text, kind) pairs, which differs from simply
        being a PATTERN if it is a group including backslash escaped chars.
        """
        return self._parts or ((self._content, PATTERN),)

    def _interrupts_group(self, char: str, chars: ParseCursor) -> bool:
        """
        Check whether the given char, just taken from chars, starts a quote or a
        parameter expansion.
        """
        if char in "'\"":
            return True
        if char == "$" and (next_char := chars.peek()):
            return next_char == "{" or (
                not self.config.require_braces and next_char in PARAM_INIT_CHARS
            )
        return False

    def _parse(self, chars: ParseCursor):
        char = chars.peek()
        if char in "*?":
            self._content = chars.take()
            return

        if char == "[":
            # Match pattern [groups]
            group_chars: list[tuple[str, int]] = []
            # The chars consumed so far, including backslashes
            source_chars: list[str] = []
            chars.take()
            for char in chars:
                if self._interrupts_group(char, chars):
                    chars.pushback(*source_chars, char)
                    self._content = "["
                    return

                source_chars.append(char)
                if char.isspace():
                    # GOTO invalid group pattern
                    break

                if char == "]":
                    if group_chars and group_chars != [("!", PATTERN)]:
                        # Group complete
                        self._parts = (
                            ("[", PATTERN),
                            *group_chars,
                            ("]", PATTERN),
                        )
                        self._content = "".join(text for text, _ in self._parts)
                        return
                    # ] at start of group is interpreted as content
                    group_chars.append((char, PATTERN))

                elif char == "\\":
                    # Backslash is always an escape when inside a group pattern
                    escaped_char = chars.take()
                    if not escaped_char:
                        raise ParseError(
                            "Invalid pattern: unexpected end of input after backslash",
                            chars,
                        )
                    source_chars.append(escaped_char)
                    group_chars.append((escaped_char, QUOTED))

                else:
                    group_chars.append((char, PATTERN))

            # invalid group pattern, pretend it never happened
            chars.pushback("[", *source_chars)
            self._cancelled = True
            return

        # This should not happen
        # ruff: noqa: B011
        assert False
        self._cancelled = True


def compose_glob_pattern(token_parts: Iterable[tuple[str, int]]) -> str | None:
    """
    Compose a python style glob pattern from the (text, kind) parts of a resolved
    token, or return None if the token turns out not to include a pattern.

    Group patterns are recognised here rather than by the parser so that they may
    include parameter expansions and quotes, as in `[${chars}]` or `["a b"]`.
    """
    chars = [
        (char, kind == PATTERN or (kind == UNQUOTED and char not in GLOB_CHARS))
        for text, kind in token_parts
        for char in text
    ]

    pattern: list[str] = []
    includes_glob = False
    index = 0
    while index < len(chars):
        char, is_special = chars[index]
        index += 1
        if char not in GLOB_CHARS:
            pattern.append(char)
        elif not is_special:
            pattern.append(f"[{char}]")
        elif char != "[":
            pattern.append(char)
            includes_glob = True
        elif group_end := _find_group_end(chars, index):
            pattern.append(_compose_group_pattern(chars[index:group_end]))
            index = group_end + 1
            includes_glob = True
        else:
            # A bracket that is never closed only matches itself
            pattern.append("[[]")

    return "".join(pattern) if includes_glob else None


def _find_group_end(chars: list[tuple[str, bool]], start: int) -> int:
    """
    Return the index of the bracket closing the group pattern with content starting
    at the given index, or 0 if the group is never closed.
    """
    if start < len(chars) and chars[start] == ("!", True):
        start += 1
    if start < len(chars) and chars[start][0] == "]":
        # A closing bracket at the start of a group is part of its content
        start += 1
    return next(
        (index for index in range(start, len(chars)) if chars[index] == ("]", True)),
        0,
    )


def _compose_group_pattern(content: list[tuple[str, bool]]) -> str:
    """
    Compose a group pattern from the chars between its brackets.

    Python style group patterns have no means of escaping, so a quoted char that
    would be special because of its position is moved to where it is not.
    """
    if all(is_special for _, is_special in content):
        return f"[{''.join(char for char, _ in content)}]"

    negation = "!" if content[0] == ("!", True) else ""
    members = content[len(negation) :]
    moved = {
        char
        for char, is_special in members
        if char == "!" or (not is_special and char in "]-")
    }
    result = "".join(
        char
        for char, is_special in members
        if char != "!" and (is_special or char not in "]-")
    )
    if result.startswith("-") or result.endswith("-"):
        # A dash at either end is not part of a range, but could end up in one
        # once other chars are moved
        moved.add("-")
        result = result.strip("-")
    if "]" in moved and not result.startswith("]"):
        result = f"]{result}"
    if "!" in moved:
        if result or negation:
            result = f"{result}!"
        elif "-" in moved:
            return "[-!]"
        else:
            # There is no way to express a group of just this char
            return "!"
    if "-" in moved:
        result = f"{result}-"

    return f"[{negation}{result}]"


class ParamExpansion(AnnotatedContentNode["ParamOperation"]):
    # The shell's special parameters other than $$. They have no meaning here, so they
    # are read as a pair and kept as written, e.g. so that $# doesn't start a comment.
    # $$ isn't included, so $$X is a literal $ followed by the value of X.
    _SPECIAL_PARAMS = frozenset("?!#-0")
    _is_special: bool = False

    @property
    def param_name(self) -> str:
        return self._content

    @property
    def is_special(self) -> bool:
        """
        Whether this is a special parameter like $?, which is kept as written.
        """
        return self._is_special

    @property
    def operation(self) -> ParamOperation | None:
        return self._annotation

    def active_argument(self, env: Mapping[str, str]) -> ParamArgument | None:
        """
        Return the operator argument if it is active for the given env, else None.

        :+ is active when the variable is set and non-empty.
        :- is active when the variable is unset or empty.
        """
        param_value = env.get(self.param_name, "")
        if self.operation and (
            (param_value and self.operation.operator == ":+")
            or (not param_value and self.operation.operator == ":-")
        ):
            return self.operation.argument
        return None

    def expand(self, env: Mapping[str, str]) -> str:
        """
        Resolve this parameter expansion to a flat string.

        Handles :- and :+ operators by delegating to the active argument's
        flatten() when applicable.
        """
        if self._is_special:
            return self._content
        if argument := self.active_argument(env):
            return argument.flatten(env)
        return env.get(self.param_name, "")

    def _parse(self, chars: ParseCursor):
        assert chars.take() == "$"

        if self.config.require_braces and chars.peek() != "{":
            # In require_braces mode, bare $VAR is not a param expansion
            chars.pushback("$")
            self._cancelled = True
            return

        if chars.peek() in self._SPECIAL_PARAMS:
            self._content = "$" + chars.take()
            self._is_special = True
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

        if chars.peek() is None:
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
        if self._quote_char == '"':
            return self._consume_double_quoted(chars)
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

            if next_char == "$":
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

            if next_char == "$":
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

            if next_char.isspace():
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

    def flatten(self, env: Mapping[str, str]) -> str:
        """
        Resolve this argument to a flat string, discarding quote structure.

        Used when the argument appears in an already-quoted context and
        word-splitting is not needed.
        """
        return "".join(
            (
                element.expand(env)
                if isinstance(element, ParamExpansion)
                else element.content
            )
            for segment in self.segments
            for element in segment
        )

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

    def resolve_tokens(
        self, env: Mapping[str, str]
    ) -> Iterator[tuple[str, str | None]]:
        """
        Resolve parameter expansions in this line against env and yield
        (token, glob_pattern) pairs.

        The token is the word as it should be passed on if not used as a pattern,
        that is after parameter expansion and quote removal. The glob_pattern is
        None unless the word includes glob syntax, either from the unquoted text of
        the word or from the value of an unquoted parameter expansion. Everything
        else in the pattern is escaped so that it only matches itself.
        """

        def finalize_token(token_parts):
            token = "".join(part for part, _ in token_parts)
            glob_pattern = (
                compose_glob_pattern(token_parts)
                if any(kind == PATTERN for _, kind in token_parts)
                else None
            )
            token_parts.clear()
            return (token, glob_pattern)

        def resolve_argument_tokens(
            argument: ParamArgument,
            token_parts: list[tuple[str, int]],
        ) -> Iterator[tuple[str, str | None]]:
            for arg_segment in argument.segments:
                if arg_segment.is_quoted:
                    for element in arg_segment:
                        if isinstance(element, ParamExpansion):
                            if flat := element.expand(env):
                                token_parts.append((flat, QUOTED))
                        else:
                            token_parts.append((element.content, QUOTED))
                else:
                    for element in arg_segment:
                        if isinstance(element, WhitespaceText):
                            if token_parts:
                                yield finalize_token(token_parts)
                        elif isinstance(element, ParamExpansion):
                            if element.is_special:
                                # Kept as written, so not globbed or word split
                                token_parts.append((element.content, QUOTED))
                            elif arg := element.active_argument(env):
                                yield from resolve_argument_tokens(arg, token_parts)
                            elif param_value := element.expand(env):
                                yield from emit_unquoted_param_value(
                                    param_value, token_parts
                                )
                        else:
                            # glob chars are not special in an operator argument
                            token_parts.extend(element.parts)

        def emit_unquoted_param_value(
            param_value: str,
            token_parts: list[tuple[str, int]],
        ) -> Iterator[tuple[str, str | None]]:
            if param_value.isspace():
                if token_parts:
                    yield finalize_token(token_parts)
                return
            if param_value[0].isspace() and token_parts:
                yield finalize_token(token_parts)
            param_words = (
                (
                    word,
                    PATTERN if any(char in word for char in GLOB_CHARS) else UNQUOTED,
                )
                for word in param_value.split()
            )
            token_parts.append(next(param_words))
            for param_word in param_words:
                if token_parts:
                    yield finalize_token(token_parts)
                token_parts.append(param_word)
            if param_value[-1].isspace() and token_parts:
                yield finalize_token(token_parts)

        for word in self:
            if isinstance(word, Comment):
                continue

            token_parts: list[tuple[str, int]] = []
            for segment in word:
                for element in segment:
                    if isinstance(element, ParamExpansion):
                        if element.is_special:
                            # Kept as written, so not globbed or word split
                            token_parts.append((element.content, QUOTED))
                            continue
                        if not segment.is_quoted and (
                            arg := element.active_argument(env)
                        ):
                            yield from resolve_argument_tokens(arg, token_parts)
                            continue
                        if param_value := element.expand(env):
                            if segment.is_quoted:
                                token_parts.append((param_value, QUOTED))
                            else:
                                yield from emit_unquoted_param_value(
                                    param_value, token_parts
                                )

                    elif isinstance(element, (Glob, UnquotedText)):
                        token_parts.extend(element.parts)

                    else:
                        token_parts.append((element.content, QUOTED))

            if token_parts:
                yield finalize_token(token_parts)

    def _parse(self, chars: ParseCursor):
        WordCls = self.get_child_node_cls(Word)
        CommentCls = self.get_child_node_cls(Comment)

        self._children = []
        for char in chars:
            if char in self.config.line_separators:
                self._terminator = char
                break

            if char.isspace():
                continue

            if char == "#":
                self._children.append(CommentCls(chars, self.config))
                self._terminator = char
                return

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
