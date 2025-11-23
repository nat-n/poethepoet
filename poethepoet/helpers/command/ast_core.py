"""
This module provides a framework for defining a hierarchical parser and AST.
See sibling ast module for an example usage.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import IO, Generic, TypeVar, cast


class ParseCursor:
    r"""
    This makes it easier to parse a text by wrapping it an abstraction like a stack,
    so the parser can pop off the next character but also push back characters that need
    to be reprocessed by a different node.

    The line and position tracking which may be used for error reporting assumes that
    whatever source we're reading the file from encodes new lines as simply '\n'.
    """

    _line: int
    _position: int
    _line_lengths: list[int]
    _source: Iterator[str]
    _pushback_stack: list[str]

    def __init__(self, source: Iterator[str]):
        self._source = source
        self._line = 0
        self._position = -1
        self._line_lengths = []
        self._pushback_stack = []

    @classmethod
    def from_file(cls, file: IO[str]):
        def iter_chars():
            while char := file.read(1):
                yield char

        return cls(iter_chars())

    @classmethod
    def from_string(cls, string: str):
        return cls(char for char in string)

    @property
    def position(self):
        return (max(0, self._line), max(0, self._position))

    def peek(self):
        if not self._pushback_stack:
            try:
                self._pushback_stack.append(next(self._source))
            except StopIteration:
                return None
        return self._pushback_stack[-1]

    def take(self):
        if self._pushback_stack:
            result = self._pushback_stack.pop()
        else:
            try:
                result = next(self._source)
            except StopIteration:
                result = None

        if result == "\n":
            self._line_lengths.append(self._position)
            self._line += 1
            self._position = -1
        else:
            self._position += 1

        return result

    def pushback(self, *items: str):
        for item in reversed(items):
            self._pushback_stack.append(item)
            if item == "\n":
                self._position = self._line_lengths.pop(0)
                self._line = max(0, self._line - 1)
            else:
                self._position -= 1

    def __iter__(self):
        return self

    def __next__(self):
        if char := self.take():
            return char
        raise StopIteration

    def __bool__(self):
        return bool(self.peek())


class ParseConfig:
    """
    A ParseConfig is passed to every AstNode in a tree, and may be used to configure
    alternative parsing behaviors, thus making to possible to declare small variations
    to the parsed syntax without having to duplicate parsing logic.
    """

    substitute_nodes: dict[type["AstNode"], type["AstNode"]]
    line_separators: str

    def __init__(
        self,
        substitute_nodes: dict[type["AstNode"], type["AstNode"]] | None = None,
        line_separators="",
    ):
        self.substitute_nodes = substitute_nodes or {}
        self.line_separators = line_separators

    def resolve_node_cls(self, klass: type["AstNode"]) -> type["AstNode"]:
        return self.substitute_nodes.get(klass, klass)


class AstNode(ABC):
    _cancelled: bool = False

    def __init__(self, chars: ParseCursor, config: ParseConfig | None = None):
        self.config = config = config or ParseConfig()
        self._parse(chars)

    @abstractmethod
    def _parse(self, chars: ParseCursor): ...

    @abstractmethod
    def pretty(self, indent: int = 0, increment: int = 4): ...

    def __bool__(self):
        return not self._cancelled

    @abstractmethod
    def __len__(self): ...


T = TypeVar("T", bound=AstNode)


class SyntaxNode(AstNode, Generic[T]):
    """
    A SyntaxNode is a branching AST node with no content of its own
    """

    _children: list[T]

    def get_child_node_cls(self, node_type: type[AstNode]) -> type[T]:
        """
        Apply Node class substitution for the given node AstNode if specified in
        the ParseConfig.
        """
        return cast("type[T]", self.config.resolve_node_cls(node_type))

    @property
    def children(self) -> tuple["SyntaxNode", ...]:
        return tuple(getattr(self, "_children", tuple()))

    def pretty(self, indent: int = 0, increment: int = 4):
        indent += increment
        return "\n".join(
            [
                f"{self.__class__.__name__}:",
                *(" " * indent + child.pretty(indent, increment) for child in self),
            ]
        )

    def __getitem__(self, index: int):
        return self._children[index]

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
    """
    A ContentNode is a terminal AST node with string content
    """

    _content: str = ""

    @property
    def content(self) -> str:
        return self._content

    def pretty(self, indent: int = 0, increment: int = 4):
        return f"{self.__class__.__name__}: {self._content!r}"

    def get_child_node_cls(self, node_type: type[AstNode]) -> type:
        """
        Apply Node class substitution for the given node AstNode if specified in
        the ParseConfig.
        """
        return cast("type", self.config.resolve_node_cls(node_type))

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


class AnnotatedContentNode(ContentNode, Generic[T]):
    """
    A AnnotatedContentNode is like a ContentNode except that it may also have a
    single child node, which is considered an annotation on the content.
    """

    _annotation: T | None = None

    def pretty(self, indent: int = 0, increment: int = 4):
        indent += increment
        content_line = f"{self.__class__.__name__}: {self._content!r}"
        if self._annotation is not None:
            return (
                f"{content_line}\n"
                f"{' ' * indent}{self._annotation.pretty(indent, increment)}"
            )
        return content_line

    def __repr__(self):
        annotation = f", {self._annotation!r}" if self._annotation else ""
        return f"{self.__class__.__name__}({self._content!r}{annotation})"

    def __eq__(self, other):
        if isinstance(other, str):
            return self._content == other
        if isinstance(other, tuple):
            if self._annotation is None:
                return (self._content,) == other
            return (self._content, self._annotation) == other
        return super().__eq__(other)


class ParseError(RuntimeError):
    line: int | None
    position: int | None

    def __init__(self, message: str, cursor: ParseCursor | None = None):
        super().__init__(message)
        self.message = message
        if cursor is not None:
            self.line, self.position = cursor.position

    @property
    def has_position(self) -> bool:
        return None not in (self.line, self.position)

    def __repr__(self):
        details = (
            f", line={self.line}, position={self.position}" if self.has_position else ""
        )
        return f'{self.__class__.__name__}("{self.message}"{details})'
