"""
Unit tests for SchemaContext.
"""

from __future__ import annotations

from typing import TypedDict

from poethepoet.options import PoeOptions
from poethepoet.options.annotations import option_annotation
from poethepoet.schema.context import SchemaContext


class _Sample(PoeOptions):
    foo: str = ""
    """The foo field — described here."""


@option_annotation
class _SampleTypedDict(TypedDict):
    bar: str
    """The bar field on the TypedDict."""


def test_register_returns_ref_string() -> None:
    ctx = SchemaContext(version="0.46.0")
    ref = ctx.register("my_thing", {"type": "object"})
    assert ref == "#/definitions/my_thing"


def test_register_stores_definition() -> None:
    ctx = SchemaContext(version="0.46.0")
    ctx.register("my_thing", {"type": "object"})
    assert ctx.definitions == {"my_thing": {"type": "object"}}


def test_register_rejects_duplicate_name_with_different_body() -> None:
    ctx = SchemaContext(version="0.46.0")
    ctx.register("name", {"type": "string"})
    import pytest

    with pytest.raises(ValueError, match="already registered"):
        ctx.register("name", {"type": "integer"})


def test_register_idempotent_for_identical_body() -> None:
    ctx = SchemaContext(version="0.46.0")
    ref1 = ctx.register("name", {"type": "string"})
    ref2 = ctx.register("name", {"type": "string"})
    assert ref1 == ref2
    assert ctx.definitions == {"name": {"type": "string"}}


def test_description_for_poeoptions_uses_mro_aware_helper() -> None:
    ctx = SchemaContext(version="0.46.0")
    assert ctx.description_for(_Sample, "foo") == "The foo field — described here."


def test_description_for_typeddict_uses_direct_extraction() -> None:
    ctx = SchemaContext(version="0.46.0")
    assert (
        ctx.description_for(_SampleTypedDict, "bar")
        == "The bar field on the TypedDict."
    )


def test_description_returns_none_for_missing_field() -> None:
    ctx = SchemaContext(version="0.46.0")
    assert ctx.description_for(_Sample, "nonexistent") is None


def test_version_stored_for_comment_line() -> None:
    ctx = SchemaContext(version="0.46.0")
    assert ctx.version == "0.46.0"
