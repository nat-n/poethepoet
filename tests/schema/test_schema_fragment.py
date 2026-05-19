"""
Unit tests for PoeOptions.__schema_fragment__ (default) and the
overrides on PoeTask and per-task subclasses.
"""

from __future__ import annotations

from typing import Annotated

import pytest

from poethepoet.options import PoeOptions
from poethepoet.options.annotations import Metadata
from poethepoet.schema.context import SchemaContext


@pytest.fixture
def ctx() -> SchemaContext:
    return SchemaContext(version="0.0.0")


class _Required(PoeOptions):
    name: str
    """The required name."""

    count: int = 0
    """The optional count (has a default)."""


class _Optional(PoeOptions):
    flag: bool | None = None
    """Optional flag."""


def test_default_emits_object_with_properties(ctx: SchemaContext) -> None:
    schema = _Required.__schema_fragment__(ctx)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"name", "count"}


def test_default_marks_required_fields(ctx: SchemaContext) -> None:
    """
    A field without a class-level default and without Optional type
    is required.
    """
    schema = _Required.__schema_fragment__(ctx)
    assert schema["required"] == ["name"]
    # `count` has a default of 0 → not required.


def test_default_attaches_descriptions(ctx: SchemaContext) -> None:
    schema = _Required.__schema_fragment__(ctx)
    assert schema["properties"]["name"]["description"] == "The required name."
    assert schema["properties"]["count"]["description"] == (
        "The optional count (has a default)."
    )


def test_default_excludes_optional_field_from_required(ctx: SchemaContext) -> None:
    schema = _Optional.__schema_fragment__(ctx)
    assert "required" in schema
    assert "flag" not in schema["required"]


def test_default_handles_metadata_constraints(ctx: SchemaContext) -> None:
    class _Constrained(PoeOptions):
        name: Annotated[str, Metadata(pattern=r"^[a-z]+$")] = ""
        """Lowercase name."""

    schema = _Constrained.__schema_fragment__(ctx)
    assert schema["properties"]["name"]["pattern"] == "^[a-z]+$"


def test_default_uses_config_name_for_property_key(ctx: SchemaContext) -> None:
    """
    When a field has Metadata(config_name=...), the schema property key
    must be the config_name, not the Python attribute name.
    """

    class _Renamed(PoeOptions):
        with_: Annotated[str, Metadata(config_name="with")] = ""

    schema = _Renamed.__schema_fragment__(ctx)
    assert "with" in schema["properties"]
    assert "with_" not in schema["properties"]


def test_default_inherits_fields_from_base_class(ctx: SchemaContext) -> None:
    """
    Approach B — full inlining. A subclass's schema_fragment contains
    both its own fields and inherited fields.
    """

    class _Child(_Required):
        extra: str = ""

    schema = _Child.__schema_fragment__(ctx)
    assert set(schema["properties"]) == {"name", "count", "extra"}
