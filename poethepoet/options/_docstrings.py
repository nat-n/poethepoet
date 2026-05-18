"""
Internal helpers for extracting per-field documentation from PoeOptions
class definitions.

The convention is PEP 257-style class attribute documentation:

    class MyOptions(PoeOptions):
        name: str = ""
        '''Description of the name field.'''

i.e. a string literal expression statement immediately following an
annotated assignment in the class body. Multi-line docstrings are
supported; leading/trailing whitespace is stripped from each line.

Extraction is per-class (the result is keyed by `cls.__name__` of the
declaring class, then by field name) and cached.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from functools import cache


@cache
def extract_field_descriptions(cls: type) -> dict[str, str]:
    """
    Parse the source of `cls` and return a mapping of field name to description
    for every annotated field whose declaration is immediately followed by a
    string-literal expression statement.

    Only fields declared directly on `cls` are returned (not inherited fields).
    The caller is responsible for MRO walking — see
    `PoeOptions.description_for_field`.
    """

    try:
        source = inspect.getsource(cls)
    except (OSError, TypeError):
        # No source available (e.g. dynamic class, REPL).
        return {}

    source = textwrap.dedent(source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    # The first node should be the ClassDef for `cls`.
    if not tree.body or not isinstance(tree.body[0], ast.ClassDef):
        return {}

    class_body = tree.body[0].body

    descriptions: dict[str, str] = {}

    for index, node in enumerate(class_body):
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        field_name = node.target.id

        # Look at the immediately following statement.
        next_index = index + 1
        if next_index >= len(class_body):
            continue
        next_node = class_body[next_index]
        if not (
            isinstance(next_node, ast.Expr)
            and isinstance(next_node.value, ast.Constant)
            and isinstance(next_node.value.value, str)
        ):
            continue

        raw = next_node.value.value
        # Normalize whitespace: strip leading/trailing blank space, dedent
        # multi-line strings, then join lines that the author wrote split
        # across the source for column-width reasons.
        descriptions[field_name] = textwrap.dedent(raw).strip()

    return descriptions
