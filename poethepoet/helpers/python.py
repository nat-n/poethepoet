"""
Helper functions for parsing and manipulating python code, as required by ScriptTask and
ExprTask.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, Any, NamedTuple, cast

if TYPE_CHECKING:
    from collections.abc import Collection, Container, Iterator

from ..exceptions import ExpressionParseError

_ALLOWED_BUILTINS = {
    "abs",
    "all",
    "any",
    "ascii",
    "bin",
    "chr",
    "dir",
    "divmod",
    "format",
    "getattr",
    "hasattr",
    "hex",
    "iter",
    "len",
    "max",
    "min",
    "next",
    "oct",
    "ord",
    "os",
    "pow",
    "repr",
    "round",
    "sorted",
    "sum",
    "None",
    "Ellipsis",
    "False",
    "True",
    "bool",
    "memoryview",
    "bytearray",
    "bytes",
    "complex",
    "dict",
    "enumerate",
    "filter",
    "float",
    "frozenset",
    "int",
    "list",
    "map",
    "range",
    "reversed",
    "set",
    "slice",
    "str",
    "tuple",
    "type",
    "zip",
}


Substitution = tuple[tuple[int, int], str]


class FunctionCall(NamedTuple):
    """
    Model for a python expression consisting of a function call
    """

    expression: str
    function_ref: str
    referenced_args: tuple[str, ...] = tuple()
    referenced_globals: tuple[str, ...] = tuple()

    @classmethod
    def parse(
        cls,
        source: str,
        arguments: Container[str],
        *,
        args_prefix: str = "__args.",
        allowed_vars: Container[str] | None = None,
    ) -> FunctionCall:
        root_node = cast("ast.Call", parse_and_validate(source, True, "script"))
        name_nodes = _validate_nodes_and_get_names(root_node, source)

        substitutions: list[Substitution] = []
        referenced_args: list[str] = []
        referenced_globals: list[str] = []
        for node in name_nodes:
            if node.id in arguments:
                substitutions.append(
                    (_get_name_node_abs_range(source, node), args_prefix + node.id)
                )
                referenced_args.append(node.id)
            elif (
                node.id in _ALLOWED_BUILTINS
                or allowed_vars is None
                or node.id in allowed_vars
            ):
                referenced_globals.append(node.id)
            else:
                raise ExpressionParseError(
                    "Invalid variable reference in script: "
                    f"{ast.get_source_segment(source, node)}"
                )

        # Prefix references to arguments with args_prefix
        expression = _apply_substitutions(source, substitutions)

        ref_parts = []
        func_node = root_node.func
        while isinstance(func_node, ast.Attribute):
            ref_parts.append(func_node.attr)
            func_node = func_node.value
        assert isinstance(func_node, ast.Name)
        function_ref = ".".join((func_node.id, *reversed(ref_parts)))

        return cls(
            expression=_clean_linebreaks(expression),
            function_ref=function_ref,
            referenced_args=tuple(referenced_args),
            referenced_globals=tuple(referenced_globals),
        )


def resolve_expression(
    source: str,
    arguments: Container[str],
    *,
    args_prefix: str = "__args.",
    allowed_vars: Container[str] = tuple(),
) -> str:
    """
    Validate function call and substitute references to arguments with their namespaced
    counterparts (e.g. `my_arg` => `__args.my_arg`).
    """

    root_node = parse_and_validate(source, False, "expr")
    name_nodes = _validate_nodes_and_get_names(root_node, source)

    substitutions: list[Substitution] = []
    for node in name_nodes:
        if node.id in arguments:
            substitutions.append(
                (_get_name_node_abs_range(source, node), args_prefix + node.id)
            )
        elif node.id not in _ALLOWED_BUILTINS and node.id not in allowed_vars:
            raise ExpressionParseError(
                "Invalid variable reference in expr: "
                f"{ast.get_source_segment(source, node)}"
            )

    # Prefix references to arguments with args_prefix
    return _clean_linebreaks(_apply_substitutions(source, substitutions))


def parse_and_validate(
    source: str, call_only: bool = True, task_type: str = "script"
) -> ast.AST:
    """
    Parse the given source into an ast, validate that is consists of a expression and
    return the root node.

    If call_only is True then require the root node to be a function call.
    """

    try:
        module = ast.parse(source)
    except SyntaxError as error:
        raise ExpressionParseError(f"Invalid {task_type} content: {source}") from error

    if len(module.body) != 1 or not isinstance(module.body[0], ast.Expr):
        raise ExpressionParseError(
            f"Expected a single python expression, instead got: {source}"
        )

    root_node = module.body[0].value

    if call_only:
        if not isinstance(root_node, ast.Call):
            raise ExpressionParseError(
                f"Expected a function call, instead got: {source}"
            )

        node = root_node.func
        while isinstance(node, ast.Attribute):
            node = node.value
        if not isinstance(node, ast.Name):
            raise ExpressionParseError(f"Invalid function reference in: {source}")

    return root_node


def format_class(attrs: dict[str, Any] | None, classname: str = "__args") -> str:
    """
    Generates source for a python class with the entries of the given dictionary
    represented as class attributes. Output is a one-liner.

    If no attributes are provided for the class then return an empty string.
    """
    if attrs is None:
        return ""
    return (
        f'{classname}=type("{classname}",(object,),'
        "{" + ",".join(f"{name!r}:{value!r}" for name, value in attrs.items()) + "});"
    )


class NoInstance:
    pass


def _validate_nodes_and_get_names(
    node: ast.AST, source: str, *, ignore_names: Collection[str] = tuple()
) -> Iterator[ast.Name]:
    """
    Walk the ast from the given node and yield all of the encountered Name nodes
    except function names from Call nodes, or variables scoped to a comprehension or
    lambda.

    Also raise if any of the banned_node_types are encountered.
    """
    banned_node_types = (
        getattr(ast, "NamedExpr", NoInstance),
        ast.Await,
        ast.Yield,
        ast.YieldFrom,
    )

    if isinstance(node, ast.Name) and node.id not in ignore_names:
        yield node

    elif isinstance(node, ast.Call):
        # skip function names

        func_ref = node.func
        while isinstance(func_ref, ast.Attribute):
            func_ref = func_ref.value
        if not isinstance(func_ref, ast.Name):
            # a function can be an attribute of the result of an expression
            yield from _validate_nodes_and_get_names(
                func_ref, source, ignore_names=ignore_names
            )

        for arg in node.args:
            yield from _validate_nodes_and_get_names(
                arg, source, ignore_names=ignore_names
            )
        for kwarg in node.keywords:
            yield from _validate_nodes_and_get_names(
                kwarg, source, ignore_names=ignore_names
            )

    elif isinstance(node, ast.Lambda):
        # ignore lambda arguments
        lambda_args = {a.arg for a in node.args.args} | set(ignore_names)
        yield from _validate_nodes_and_get_names(
            node.body, source, ignore_names=lambda_args
        )

    elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        # ignore comprehension/generator scoped variables

        comp_vars = {
            gen_node.id
            for comp_node in node.generators
            for gen_node in ast.walk(comp_node.target)
            if isinstance(gen_node, ast.Name)
        } | set(ignore_names)

        if isinstance(node, ast.DictComp):
            yield from _validate_nodes_and_get_names(
                node.key, source, ignore_names=comp_vars
            )
        else:
            yield from _validate_nodes_and_get_names(
                node.elt, source, ignore_names=comp_vars
            )
        for comp_node in node.generators:
            yield from _validate_nodes_and_get_names(
                comp_node, source, ignore_names=comp_vars
            )

    elif isinstance(node, banned_node_types):
        if isinstance(
            node,
            getattr(ast, "NamedExpr", NoInstance),
        ):
            raise ExpressionParseError(
                f"Expression should not include named expressions: {source}"
            )
        if isinstance(node, ast.Await):
            raise ExpressionParseError(f"Expression should not include await: {source}")
        raise ExpressionParseError(f"Expression should not include yield: {source}")

    elif node:
        for child_node in ast.iter_child_nodes(node):
            yield from _validate_nodes_and_get_names(
                child_node, source, ignore_names=ignore_names
            )


def _apply_substitutions(content: str, subs: list[Substitution]) -> str:
    """
    Returns a copy of content with all of the substitutions applied.
    Uses a single pass for efficiency.
    """
    cursor = 0
    segments: list[str] = []

    for (start, end), replacement in sorted(subs, key=lambda x: x[0][0]):
        in_between = content[cursor:start]
        segments.extend((in_between, replacement))
        cursor += len(in_between) + (end - start)

    segments.append(content[cursor:])

    return "".join(segments)


# This pattern matches the sequence of chars from the beginning of the string that are
# *probably* a valid identifier
IDENTIFIER_PATTERN = r"[^\s\!-\/\:-\@\[-\^\{-\~`]+"


def _get_name_node_abs_range(source: str, node: ast.Name):
    """
    Find the absolute start and end offsets of the given name node in the source.
    """

    source_lines = re.findall(r".*?(?:\r\n|\r|\n)", source + "\n")
    prev_lines_offset = sum(len(line) for line in source_lines[: node.lineno - 1])
    own_line_offset = len(
        source_lines[node.lineno - 1].encode()[: node.col_offset].decode()
    )
    total_start_chars_offset = prev_lines_offset + own_line_offset

    name_content = re.match(  # type: ignore[union-attr]
        IDENTIFIER_PATTERN, source[total_start_chars_offset:]
    ).group()
    while not name_content.isidentifier() and name_content:
        name_content = name_content[:-1]

    return (total_start_chars_offset, total_start_chars_offset + len(name_content))


def _clean_linebreaks(expression: str):
    """
    Strip out any new lines because they can be problematic on windows
    """
    expression = re.sub(r"((\r\n|\r|\n) | (\r\n|\r|\n))", " ", expression)
    return re.sub(r"(\r\n|\r|\n)", " ", expression)
