import ast
from itertools import chain
from typing import Any, Container, Dict, List, Optional, Tuple, Union
from ..exceptions import ScriptParseError

_BUILTINS_WHITELIST = [
    "abs",
    "all",
    "any",
    "ascii",
    "bin",
    "chr",
    "dir",
    "divmod",
    "environ",
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
]

ARGS_PREFIX = "args."


Substitution = Tuple[Tuple[int, int], str]


def format_args_class(args: Optional[Dict[str, Any]]) -> str:
    if args is None:
        return ""
    return (
        "class args:\n"
        + "\n".join(f"    {name} = {value!r}" for name, value in args.items())
        + "\n"
    )


def parse_script_content(
    content: str, args: Optional[Dict[str, Any]]
) -> Union[Tuple[str, str], Tuple[None, None]]:
    """
    Returns the module to load, and the function call to execute.

    Will raise an exception if the function call contains invalid syntax or references
    variables that are not in scope.
    """
    try:
        target_module, target_ref = content.split(":", 1)
    except ValueError:
        return None, None

    if target_ref.isidentifier():
        if args:
            return target_module, f"{target_ref}(**({args}))"
        return target_module, f"{target_ref}()"

    return target_module, resolve_function_call(target_ref, set(args or tuple()))


def resolve_function_call(expression: str, arguments: Container[str]):
    """
    Validate function call and substitute references to arguments with their namespaced
    counterparts (e.g. `my_arg` => `args.my_arg`).
    """

    try:
        module = ast.parse(expression)
    except SyntaxError as error:
        raise ScriptParseError(f"Invalid script content: {expression}") from error

    assert len(module.body) == 1

    call_node = module.body[0].value
    assert isinstance(call_node, ast.Call)

    _validate_func(call_node.func, expression)

    substitutions: List[Substitution] = []

    # Collect all the variables
    name_nodes = chain(
        (
            node
            for arg in call_node.args
            for node in ast.walk(arg)
            if isinstance(node, ast.Name)
        ),
        (
            node
            for kwarg in call_node.keywords
            for node in ast.walk(kwarg.value)
            if isinstance(node, ast.Name)
        ),
    )
    for node in name_nodes:
        if node.id in _BUILTINS_WHITELIST:
            # builtin values have precedence over unqualified args
            continue
        if node.id in arguments:
            substitutions.append(
                ((node.col_offset, node.end_col_offset), ARGS_PREFIX + node.id)
            )
        else:
            raise ScriptParseError(
                f"Invalid variable reference in script: {_get_node_text(node, expression)}"
            )

    # Prefix references to arguments with ARGS_PREFIX
    return apply_substitutions(expression, substitutions)


# TODO: unit test this


def _validate_func(func_node: ast.AST, expression: str):
    """
    Validate function ref is just Attribute and Name Nodes
    """
    value = func_node
    while isinstance(value, ast.Attribute):
        value = value.value
    if not isinstance(value, ast.Name):
        raise ScriptParseError(
            f"Invalid function reference: {_get_node_text(func_node, expression)}"
        )


# TODO: unit test this


def _get_node_text(func_node: ast.AST, expression: str):
    lines = expression.splitlines()[func_node.lineno - 1 : func_node.end_lineno]
    inv_end_col_offset = len(lines[-1]) - func_node.end_col_offset
    return "\n".join(lines)[func_node.col_offset : -inv_end_col_offset]


# TODO: unit test this


def apply_substitutions(content: str, subs: List[Substitution]):
    """
    Returns a copy of input with all of the substitutions applied
    """
    cursor = 0
    fragments = []

    for ((start, end), replacement) in sorted(subs, key=lambda x: x[0][0]):
        in_between = content[cursor:start]
        fragments.extend((in_between, replacement))
        cursor += len(in_between) + (end - start)

    fragments.append(content[cursor:])

    return "".join(fragments)
