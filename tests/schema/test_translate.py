"""
Unit tests for the TypeAnnotation → JSON Schema translator.

Each translator is tested in isolation. Cross-cutting compositions
(unions of multiple variants, tagged unions over the `type:` key) live
in tests/schema/test_schema_fragment.py and tests/schema/test_meta.py.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

import pytest

from poethepoet.options.annotations import Metadata, TypeAnnotation
from poethepoet.schema.context import SchemaContext
from poethepoet.schema.translate import translate_type


@pytest.fixture
def ctx() -> SchemaContext:
    return SchemaContext(version="0.0.0")


# --- PrimitiveType ---

def test_str_to_string_schema(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(str)
    assert translate_type(annotation, ctx) == {"type": "string"}


def test_int_to_integer_schema(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(int)
    assert translate_type(annotation, ctx) == {"type": "integer"}


def test_float_to_number_schema(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(float)
    assert translate_type(annotation, ctx) == {"type": "number"}


def test_bool_to_boolean_schema(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(bool)
    assert translate_type(annotation, ctx) == {"type": "boolean"}


# --- Metadata-driven constraints on primitives ---

def test_str_with_pattern(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(
        Annotated[str, Metadata(pattern=r"^[a-z]+$")]
    )
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "string", "pattern": "^[a-z]+$"}


def test_str_with_min_max_length(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(
        Annotated[str, Metadata(min_length=1, max_length=50)]
    )
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "string", "minLength": 1, "maxLength": 50}


def test_int_with_minimum_maximum(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(
        Annotated[int, Metadata(minimum=-2, maximum=2)]
    )
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "integer", "minimum": -2, "maximum": 2}


def test_int_with_zero_minimum_not_dropped(ctx: SchemaContext) -> None:
    """
    Guards against the falsy-value regression that Phase 1 fixed in
    metadata_get; minimum=0 must appear in the output.
    """
    annotation = TypeAnnotation.parse(
        Annotated[int, Metadata(minimum=0)]
    )
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "integer", "minimum": 0}


def test_str_with_examples(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(
        Annotated[str, Metadata(examples=["foo", "bar"])]
    )
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "string", "examples": ["foo", "bar"]}


# --- LiteralType ---

def test_string_literal_to_enum(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(Literal["a", "b", "c"])
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "string", "enum": ["a", "b", "c"]}


def test_int_literal_to_enum(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(Literal[1, 2, 3])
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "integer", "enum": [1, 2, 3]}


def test_mixed_literal_drops_type_field(ctx: SchemaContext) -> None:
    """
    When literal values span multiple JSON types, only emit `enum`
    (no `type:`).
    """
    annotation = TypeAnnotation.parse(Literal[True, "yes"])
    schema = translate_type(annotation, ctx)
    assert schema == {"enum": [True, "yes"]}


# --- AnyType ---

def test_any_to_empty_schema(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(Any)
    assert translate_type(annotation, ctx) == {}


# --- NoneType ---

def test_none_translates_to_null_schema(ctx: SchemaContext) -> None:
    """
    NoneType isn't usually emitted standalone (Optional collapse happens
    at the UnionType level), but the translator should still produce a
    valid schema for it for completeness.
    """
    annotation = TypeAnnotation.parse(None)
    assert translate_type(annotation, ctx) == {"type": "null"}


# --- ShellInterpreter alias (smoke test) ---

def test_shell_interpreter_literal_alias_translates(ctx: SchemaContext) -> None:
    """
    Verifies the register_type_alias mechanism from Phase 1 works
    end-to-end: ShellInterpreter is a registered alias for a Literal,
    and translation should produce the expected enum schema.
    """
    from poethepoet.config.partition import ShellInterpreter

    annotation = TypeAnnotation.parse(ShellInterpreter)
    schema = translate_type(annotation, ctx)
    assert schema["type"] == "string"
    assert set(schema["enum"]) == {
        "posix", "sh", "bash", "zsh", "fish", "pwsh", "powershell", "python",
    }
