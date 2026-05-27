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
    annotation = TypeAnnotation.parse(Annotated[str, Metadata(pattern=r"^[a-z]+$")])
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "string", "pattern": "^[a-z]+$"}


def test_str_with_min_max_length(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(
        Annotated[str, Metadata(min_length=1, max_length=50)]
    )
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "string", "minLength": 1, "maxLength": 50}


def test_int_with_minimum_maximum(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(Annotated[int, Metadata(minimum=-2, maximum=2)])
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "integer", "minimum": -2, "maximum": 2}


def test_int_with_zero_minimum_not_dropped(ctx: SchemaContext) -> None:
    """
    Guards against falsy-value handling in metadata_get;
    minimum=0 must appear in the output, not be silently dropped.
    """
    annotation = TypeAnnotation.parse(Annotated[int, Metadata(minimum=0)])
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "integer", "minimum": 0}


def test_str_with_examples(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(Annotated[str, Metadata(examples=["foo", "bar"])])
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
    Verifies the register_type_alias mechanism works end-to-end:
    ShellInterpreter is a registered alias for a Literal, and translation
    should produce the expected enum schema.
    """
    from poethepoet.config.partition import ShellInterpreter

    annotation = TypeAnnotation.parse(ShellInterpreter)
    schema = translate_type(annotation, ctx)
    assert schema["type"] == "string"
    assert set(schema["enum"]) == {
        "posix",
        "sh",
        "bash",
        "zsh",
        "fish",
        "pwsh",
        "powershell",
        "python",
    }


# --- ListType ---


def test_list_of_str_to_array_schema(ctx: SchemaContext) -> None:
    from collections.abc import Sequence

    annotation = TypeAnnotation.parse(Sequence[str])
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "array", "items": {"type": "string"}}


def test_list_with_min_max_items(ctx: SchemaContext) -> None:
    from collections.abc import Sequence

    annotation = TypeAnnotation.parse(
        Annotated[Sequence[str], Metadata(min_items=1, max_items=10)]
    )
    schema = translate_type(annotation, ctx)
    assert schema == {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 1,
        "maxItems": 10,
    }


def test_untyped_list_to_unconstrained_array(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(list)
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "array"}


# --- DictType ---


def test_dict_str_to_str_schema(ctx: SchemaContext) -> None:
    from collections.abc import Mapping

    annotation = TypeAnnotation.parse(Mapping[str, str])
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "object", "additionalProperties": {"type": "string"}}


def test_untyped_dict_to_unconstrained_object(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(dict)
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "object"}


# --- TypedDictType ---


def test_typeddict_emits_properties_and_required(ctx: SchemaContext) -> None:
    from typing import TypedDict

    from poethepoet.options.annotations import option_annotation

    @option_annotation
    class _ExampleTD(TypedDict):
        name: str
        """The name."""

        count: int

    _ExampleTD.__optional_keys__ = frozenset()  # all required

    annotation = TypeAnnotation.parse(_ExampleTD)
    schema = translate_type(annotation, ctx)

    # Properties and required keys
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["name"] == {
        "type": "string",
        "description": "The name.",
    }
    assert schema["properties"]["count"] == {"type": "integer"}
    assert sorted(schema["required"]) == ["count", "name"]


def test_typeddict_with_optional_keys_omits_from_required(ctx: SchemaContext) -> None:
    from typing import TypedDict

    from poethepoet.options.annotations import option_annotation

    @option_annotation
    class _OptionalTD(TypedDict, total=False):
        a: str

    annotation = TypeAnnotation.parse(_OptionalTD)
    schema = translate_type(annotation, ctx)
    assert schema["required"] == []


def test_typeddict_description_from_class_attribute_docstring(
    ctx: SchemaContext,
) -> None:
    """
    Verifies that TypedDict descriptions are extracted (not via the
    PoeOptions MRO path, since TypedDicts aren't PoeOptions subclasses).
    """
    from typing import TypedDict

    from poethepoet.options.annotations import option_annotation

    @option_annotation
    class _DescribedTD(TypedDict):
        field: str
        """This description should appear in the schema."""

    annotation = TypeAnnotation.parse(_DescribedTD)
    schema = translate_type(annotation, ctx)
    assert schema["properties"]["field"]["description"] == (
        "This description should appear in the schema."
    )


# --- UnionType ---


def test_union_of_str_and_int_to_anyof(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(str | int)
    schema = translate_type(annotation, ctx)
    assert schema == {
        "anyOf": [
            {"type": "string"},
            {"type": "integer"},
        ]
    }


def test_optional_str_collapses_to_str_schema(ctx: SchemaContext) -> None:
    """
    `Optional[str]` (i.e. `str | None`) translates to just the `str`
    schema; the schema-fragment hook handles "field not required" at the
    object level via the parent's `required` list.
    """
    annotation = TypeAnnotation.parse(str | None)
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "string"}


def test_optional_complex_union_drops_none_branch(ctx: SchemaContext) -> None:
    """A multi-branch union with None should drop the None branch."""
    annotation = TypeAnnotation.parse(str | int | None)  # str | int | None
    schema = translate_type(annotation, ctx)
    assert schema == {
        "anyOf": [
            {"type": "string"},
            {"type": "integer"},
        ]
    }


def test_pure_none_union_is_null(ctx: SchemaContext) -> None:
    """Edge case: a union containing only None resolves to null."""
    annotation = TypeAnnotation.parse(type(None) | None)
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "null"}


# --- Metadata.type_constraints() ↔ translator round-trip ---


# Map snake_case constraint names to the JSON Schema keywords the
# translator must emit. Kept inside the test module so the asserted
# contract lives next to the test, not buried in the translator.
_CONSTRAINT_TO_JSON_KEY: dict[str, str] = {
    "pattern": "pattern",
    "min_length": "minLength",
    "max_length": "maxLength",
    "minimum": "minimum",
    "maximum": "maximum",
    "min_items": "minItems",
    "max_items": "maxItems",
}


# Representative Python annotation for each JSON Schema type the
# constraint table references. Used to build a sample annotation per
# (constraint, type) pair so we can ask the translator to handle it.
def _annotation_for_json_type(json_type: str) -> Any:
    from collections.abc import Sequence

    return {
        "string": str,
        "integer": int,
        "number": float,
        "array": Sequence[str],
    }[json_type]


# Sample value used when applying a constraint. Picked to be obviously
# non-default so a forgotten emission shows up as a missing key rather
# than a value-comparison flake (e.g. min_items=0 might be the zero
# value of some implicit code path).
_CONSTRAINT_SAMPLE_VALUE: dict[str, Any] = {
    "pattern": r"\d+",
    "min_length": 1,
    "max_length": 50,
    "minimum": 5,
    "maximum": 100,
    "min_items": 1,
    "max_items": 10,
}


def _round_trip_cases() -> list[tuple[str, str]]:
    """
    Flatten Metadata.type_constraints() into (constraint, json_type)
    pairs so each cell of the table becomes a parametrized test case.
    """
    return [
        (constraint, json_type)
        for constraint, json_types in Metadata.type_constraints().items()
        for json_type in sorted(json_types)
    ]


@pytest.mark.parametrize(("constraint", "json_type"), _round_trip_cases())
def test_metadata_type_constraints_round_trip(
    constraint: str, json_type: str, ctx: SchemaContext
) -> None:
    """
    Every cell of ``Metadata.type_constraints()`` must round-trip
    through the translator: applying the constraint as ``Metadata(**{
    constraint: value})`` to an annotation of the declared JSON type
    produces a schema fragment containing the corresponding JSON
    Schema keyword with that value.

    This guards against silent drift between the constraint table and
    the per-type translator branches (the ``min_items`` vs
    ``min_length`` typo that previously dropped ``minItems`` on shell
    interpreter arrays would have been caught here).
    """
    py_type = _annotation_for_json_type(json_type)
    sample = _CONSTRAINT_SAMPLE_VALUE[constraint]
    expected_key = _CONSTRAINT_TO_JSON_KEY[constraint]

    annotation = TypeAnnotation.parse(
        Annotated[py_type, Metadata(**{constraint: sample})]
    )
    schema = translate_type(annotation, ctx)
    assert schema.get(expected_key) == sample, (
        f"{constraint!r} on JSON type {json_type!r} did not produce "
        f"{expected_key!r}={sample!r}: {schema!r}"
    )


def test_metadata_type_constraints_keys_match_constraint_table() -> None:
    """
    The local ``_CONSTRAINT_TO_JSON_KEY`` mapping must list exactly
    the constraints declared in ``Metadata.type_constraints()``. If a
    new constraint is added to the runtime table without a JSON-key
    mapping (or vice versa), this test fails — surfacing the gap
    instead of letting the parametrized round-trip silently skip it.
    """
    table_keys = set(Metadata.type_constraints().keys())
    mapping_keys = set(_CONSTRAINT_TO_JSON_KEY.keys())
    assert table_keys == mapping_keys, (
        f"constraint table {table_keys!r} and JSON-key mapping "
        f"{mapping_keys!r} are out of sync"
    )


def test_all_type_annotation_subclasses_have_a_translator(ctx: SchemaContext) -> None:
    """
    If a new TypeAnnotation subclass is introduced, this test will fail
    until a translator branch is added.
    """
    # Walk the TypeAnnotation subclass tree.
    to_check = [TypeAnnotation]
    leaves: list[type] = []
    while to_check:
        cls = to_check.pop()
        subclasses = cls.__subclasses__()
        if not subclasses:
            leaves.append(cls)
        else:
            to_check.extend(subclasses)

    # For each leaf, construct a representative annotation and translate.
    # The exact construction varies per subclass; this loop simply asserts
    # that NotImplementedError is never raised for known subclasses.
    representative_annotations = {
        "PrimitiveType": TypeAnnotation.parse(str),
        "LiteralType": TypeAnnotation.parse(Literal["a"]),
        "AnyType": TypeAnnotation.parse(Any),
        "NoneType": TypeAnnotation.parse(None),
        "ListType": TypeAnnotation.parse(list),
        "DictType": TypeAnnotation.parse(dict),
        # TypedDictType and UnionType are exercised by dedicated tests.
    }

    for cls in leaves:
        name = cls.__name__
        if name in ("TypedDictType", "UnionType"):
            continue  # exercised by dedicated tests
        annotation = representative_annotations.get(name)
        assert annotation is not None, (
            f"No representative annotation for {name} — add one to keep "
            "this comprehensiveness test honest."
        )
        # Translation should not raise.
        result = translate_type(annotation, ctx)
        assert isinstance(result, dict)
