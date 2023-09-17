r"""
This module implements a heirarchical parser and AST along the lines of the
following grammar which is a subset of bash syntax.

script                  : line*
line                    : word* comment?
word                    : segment*
segment                 : UNQUOTED_CONTENT | single_quoted_sement | double_quoted_sement

unquoted_sement         : UNQUOTED_CONTENT | param_expansion | glob
single_quoted_sement    : "'" SINGLE_QUOTED_CONTENT "'"
double_quoted_sement    : "\"" (DOUBLE_QUOTED_CONTENT | param_expansion) "\""

comment                 : /#[^\n\r\f\v]*/
glob                    : "?" | "*" | "[" /(\!?\]([^\s\]\\]|\\.)*|([^\s\]\\]|\\.)+)*/ "]"

UNQUOTED_CONTENT        : /[^\s;#*?[$]+/
SINGLE_QUOTED_CONTENT   : /[^']+/
DOUBLE_QUOTED_CONTENT   : /([^\$"]|\[\$"])+/
"""

from abc import ABC, abstractmethod
from typing import (
    IO,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

PARAM_INIT_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_"
PARAM_CHARS = PARAM_INIT_CHARS + "0123456789"
LINE_BREAK_CHARS = "\r\n\f\v"
LINE_SEP_CHARS = LINE_BREAK_CHARS + ";"


class ParseCursor:
    _line: int
    _position: int
    _source: Iterator[str]
    _pushback_stack: List[str]

    def __init__(self, source: Iterator[str]):
        self._source = source
        self._line = 0
        self._position = 0
        self._pushback_stack = []

    @classmethod
    def from_file(cls, file: IO[str]):
        def iter_chars():
            while char := file.read(1):
                yield char

        return cls(iter_chars())

    def pushback(self, *items: str):
        for item in reversed(items):
            # TODO: rewind _line and _position
            # HOW to get length of previous line which pushback a line break?
            #   would need to keep a stack of all previous line lengths to be sure!?
            self._pushback_stack.append(item)

    def peek(self):
        if not self._pushback_stack:
            try:
                self._pushback_stack.append(next(self._source))
            except StopIteration:
                return None
        return self._pushback_stack[-1]

    def take(self):
        # TODO: update _line and _position
        if self._pushback_stack:
            return self._pushback_stack.pop()

        try:
            return next(self._source)
        except StopIteration:
            return None

    def __iter__(self):
        return self

    def __next__(self):
        if char := self.take():
            return char
        raise StopIteration

    def __bool__(self):
        return bool(self.peek())


class ParseConfig:
    substitute_nodes: Dict[Type["AstNode"], Type["AstNode"]]
    line_seperators: str

    def __init__(
        self,
        substitute_nodes: Optional[Dict[Type["AstNode"], Type["AstNode"]]] = None,
        line_seperators=LINE_SEP_CHARS,
    ):
        self.substitute_nodes = substitute_nodes or {}
        self.line_seperators = line_seperators

    def resolve_node_cls(self, klass: Type["AstNode"]) -> Type["AstNode"]:
        return self.substitute_nodes.get(klass, klass)


class AstNode(ABC):
    _cancelled: bool = False

    def __init__(self, chars: ParseCursor, config: ParseConfig = ParseConfig()):
        self.config = config
        self._parse(chars)

    @abstractmethod
    def _parse(self, chars: ParseCursor):
        ...

    @abstractmethod
    def pretty(self, indent: int = 0, increment: int = 4):
        ...

    def __bool__(self):
        return not self._cancelled

    @abstractmethod
    def __len__(self):
        ...


T = TypeVar("T")


class SyntaxNode(AstNode, Generic[T]):
    _children: List[T]

    def get_child_node_cls(self, node_type: Type[AstNode]) -> Type[T]:
        """
        Apply Node class substitution for the given node AstNode if specified in
        the ParseConfig.
        """
        return cast(Type[T], self.config.resolve_node_cls(node_type))

    @property
    def children(self) -> Tuple["SyntaxNode", ...]:
        return tuple(getattr(self, "_children", tuple()))

    def pretty(self, indent: int = 0, increment: int = 4):
        indent += increment
        lines = [f"{self.__class__.__name__}:"]
        for child in self:
            lines.append(" " * indent + child.pretty(indent))

        return "\n".join(lines)

    def __iter__(self):
        return iter(self._children)

    def __len__(self):
        return len(self._children)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({', '.join(repr(c) for c in self._children)})"
        )

    def __eq__(self, other):
        if isinstance(other, tuple):
            return self.children == other
        return super().__eq__(other)


class ContentNode(AstNode):
    _content: str = ""

    @property
    def content(self) -> str:
        return self._content

    def pretty(self, indent: int = 0, increment: int = 4):
        return f"{self.__class__.__name__}: {self._content!r}"

    def __str__(self):
        return self._content

    def __len__(self):
        return len(self._content)

    def __repr__(self):
        return f"{self.__class__.__name__}({self._content!r})"

    def __eq__(self, other):
        if isinstance(other, str):
            return self._content == other
        return super().__eq__(other)


class SingleQuotedText(ContentNode):
    def _parse(self, chars: ParseCursor):
        content: List[str] = []
        for char in chars:
            if char == "'":
                chars.pushback(char)
                self._content = "".join(content)
                return

            content.append(char)


class DoubleQuotedText(ContentNode):
    def _parse(self, chars: ParseCursor):
        content: List[str] = []
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
    def _parse(self, chars: ParseCursor):
        content: List[str] = []
        for char in chars:
            if char == "\\":
                # Backslash is always an escape when outside of quotes
                escaped_char = chars.take()
                if not escaped_char:
                    raise ParseError(
                        "Invalid pattern: unexpected end of input after backslash",
                        chars,
                    )
                content.append(escaped_char)
                continue

            elif char.isspace() or char in "'\"#$?*[":
                chars.pushback(char)
                break

            content.append(char)

        if content:
            self._content = "".join(content)
        else:
            self._cancelled = True


class Glob(ContentNode):
    """
    This implementation recognises a subset of bash style glob patterns.
    """

    # This pattern is equivalent to what this node might parse
    PATTERN = r"(?P<simple>[\?\*])|(?P<complex>\[(?:\!?\](?:[^\s\]\\]|\\.)*|(?:[^\s\]\\]|\\.)+)\])"

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
            assert False
            self._cancelled = True


class PythonGlob(Glob):
    """
    This implementation recognises glob patterns supports by the python standard library glob module.

    The key divergences from bash style pattern matching are that within square bracket patterns:
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
            group_chars: List[str] = []
            chars.take()
            for char in chars:
                if char == "]":
                    if group_chars:
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
            assert False
            self._cancelled = True


class ParamExpansion(ContentNode):
    @property
    def param_name(self) -> str:
        return self._content

    def _parse(self, chars: ParseCursor):
        assert chars.take() == "$"

        param: List[str] = []
        if chars.peek() == "{":
            chars.take()
            for char in chars:
                if char == "}":
                    if not param:
                        raise ParseError("Bad substitution: ${}", chars)

                    self._content = "".join(param)
                    return

                if param:
                    if char not in PARAM_CHARS:
                        raise ParseError(
                            f"Illegal character in parameter name {char!r}", chars
                        )

                    param.append(char)

                elif char in PARAM_INIT_CHARS:
                    param.append(char)

                else:
                    raise ParseError(
                        f"Illegal first character in parameter name {char!r}", chars
                    )

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
    _quote_char: Optional[Literal['"', "'"]]

    @property
    def is_quoted(self) -> bool:
        return bool(self._quote_char)

    @property
    def is_singlequoted(self) -> bool:
        return self._quote_char == "'"

    @property
    def is_doublequoted(self) -> bool:
        return self._quote_char == '"'

    def _parse(self, chars: ParseCursor):
        self._quote_char = next(chars) if chars.peek() in "'\"" else None
        self._children = []

        if self._quote_char == "'":
            return self.__consume_single_quoted(chars)
        elif self._quote_char == '"':
            return self.__consume_double_quoted(chars)
        else:
            return self.__consume_unquoted(chars)

    def __consume_single_quoted(self, chars):
        # pylint: disable=invalid-name
        SingleQuotedTextCls = self.get_child_node_cls(SingleQuotedText)

        while next_char := chars.peek():
            if next_char == "'":
                chars.take()
                return

            self._children.append(SingleQuotedTextCls(chars, self.config))

        raise ParseError("Unexpected end of input with unmatched single quote.")

    def __consume_double_quoted(self, chars):
        # pylint: disable=invalid-name
        DoubleQuotedTextCls = self.get_child_node_cls(DoubleQuotedText)
        # pylint: disable=invalid-name
        ParamExpansionCls = self.get_child_node_cls(ParamExpansion)

        while next_char := chars.peek():
            if next_char == '"':
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

        raise ParseError("Unexpected end of input with unmatched double quote.")

    def __consume_unquoted(self, chars):
        # pylint: disable=invalid-name
        UnquotedTextCls = self.get_child_node_cls(UnquotedText)
        # pylint: disable=invalid-name
        GlobCls = self.get_child_node_cls(Glob)
        # pylint: disable=invalid-name
        ParamExpansionCls = self.get_child_node_cls(ParamExpansion)

        while next_char := chars.peek():
            if next_char.isspace() or next_char in "'\"#":
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


class Word(SyntaxNode[Segment]):
    @property
    def segments(self) -> Tuple[Segment, ...]:
        return tuple(self._children)

    def _parse(self, chars: ParseCursor):
        # pylint: disable=invalid-name
        SegmentCls = self.get_child_node_cls(Segment)

        self._children = []

        while next_char := chars.peek():
            if next_char.isspace() or next_char in ";#":
                if not self._children:
                    self._cancelled = True
                return

            self._children.append(SegmentCls(chars, self.config))


class Line(SyntaxNode[Union[Word, Comment]]):
    @property
    def words(self) -> Tuple[Word, ...]:
        if self._children and isinstance(self._children[-1], Comment):
            return tuple(cast(Iterable[Word], self._children[:-1]))
        return tuple(cast(Iterable[Word], self._children))

    @property
    def comment(self) -> str:
        if self._children and isinstance(self._children[-1], Comment):
            return self._children[-1].comment
        return ""

    def _parse(self, chars: ParseCursor):
        # pylint: disable=invalid-name
        WordCls = self.get_child_node_cls(Word)
        # pylint: disable=invalid-name
        CommentCls = self.get_child_node_cls(Comment)

        self._children = []
        for char in chars:
            if char in self.config.line_seperators:
                break

            elif char.isspace():
                continue

            elif char == "#":
                self._children.append(CommentCls(chars, self.config))
                return

            else:
                chars.pushback(char)
                if word := WordCls(chars, self.config):
                    self._children.append(word)

        if not self._children:
            self._cancelled = True


class Script(SyntaxNode[Line]):
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
        # pylint: disable=invalid-name
        LineCls = self.get_child_node_cls(Line)

        self._children = []
        while next_char := chars.peek():
            if next_char in self.config.line_seperators:
                chars.take()
                continue

            if line_node := LineCls(chars, self.config):
                self._children.append(line_node)


class ParseError(RuntimeError):
    pass
