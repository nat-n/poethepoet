import ast
from itertools import chain
import re
import sys
from typing import Any, Container, Dict, Iterator, List, Optional, Tuple, Union
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


def resolve_function_call(source: str, arguments: Container[str]):
    """
    Validate function call and substitute references to arguments with their namespaced
    counterparts (e.g. `my_arg` => `args.my_arg`).
    """

    call_node = _parse_and_validate(source)

    substitutions: List[Substitution] = []

    # Collect all the variables
    name_nodes: Iterator[ast.Name] = chain(
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
                (
                    (
                        node.col_offset,
                        node.col_offset + len(_get_name_source_segment(source, node)),
                    ),
                    ARGS_PREFIX + node.id,
                )
            )
        else:
            raise ScriptParseError(
                f"Invalid variable reference in script: {_get_name_source_segment(source, node)}"
            )

    # Prefix references to arguments with ARGS_PREFIX
    return _apply_substitutions(source, substitutions)


# TODO: unit test this
def _parse_and_validate(source: str):
    """
    Parse the given source into an ast, validate that is consists of a single function
    call, and return the Call node.
    """

    try:
        module = ast.parse(source)
    except SyntaxError as error:
        raise ScriptParseError(f"Invalid script content: {source}") from error

    if len(module.body) != 1:
        raise ScriptParseError(
            f"Expected a single python expression, instead got: {source}"
        )

    first_statement = module.body[0]
    if not isinstance(first_statement, ast.Expr):
        raise ScriptParseError(f"Expected a function call, instead got: {source}")

    call_node = first_statement.value
    if not isinstance(call_node, ast.Call):
        raise ScriptParseError(f"Expected a function call, instead got: {source}")

    node = call_node.func
    while isinstance(node, ast.Attribute):
        node = node.value
    if not isinstance(node, ast.Name):
        raise ScriptParseError(f"Invalid function reference in: {source}")

    return call_node


# TODO: unit test this
def _apply_substitutions(content: str, subs: List[Substitution]):
    """
    Returns a copy of input with all of the substitutions applied
    """
    cursor = 0
    segments: List[str] = []

    for ((start, end), replacement) in sorted(subs, key=lambda x: x[0][0]):
        in_between = content[cursor:start]
        segments.extend((in_between, replacement))
        cursor += len(in_between) + (end - start)

    segments.append(content[cursor:])

    return "".join(segments)


# This pattern matches the sequence of chars from the begining of the string that are
# *probably* a valid identifier
IDENTIFIER_PATTERN = r"[^\s\!-\/\:-\@\[-\^\{-\~`]+"


def _get_name_source_segment(source: str, node: ast.Name):
    """
    Before python 3.8 the ast module didn't allow for easily identifying the source
    segment of a node, so this function provides this functionality specifically for
    name nodes as needed here.

    The fallback logic is specialised for name nodes which cannot span multiple lines
    and must be valid identifiers. It is expected to be correct in all cases, and
    performant in common cases.
    """
    if sys.version_info.minor >= 8:
        return ast.get_source_segment(source, node)  # type: ignore

    partial_result = (
        re.split(r"(?:\r\n|\r|\n)", source)[node.lineno - 1]
        .encode()[node.col_offset :]
        .decode()
    )

    # The name probably extends to the first ascii char outside of [a-zA-Z\d_]
    # regex will always match with valid arguments to this function
    partial_result = re.match(IDENTIFIER_PATTERN, partial_result).group()  # type: ignore

    # This bit is a nasty hack, but probably always gets skipped
    while not partial_result.isidentifier() and partial_result:
        partial_result = partial_result[:-1]

    return partial_result
