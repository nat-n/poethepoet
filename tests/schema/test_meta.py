"""
Meta-validation: the generated schema is itself a valid JSON Schema
draft-07, and has the structural properties we expect at the root.
"""

from __future__ import annotations

from jsonschema import Draft7Validator

from poethepoet.schema import build_schema


def test_generated_schema_is_valid_draft7() -> None:
    """
    Run the meta-schema check from jsonschema. Catches malformed schemas
    that would break editor tooling.
    """
    schema = build_schema()
    Draft7Validator.check_schema(schema)


def test_root_has_required_top_level_keys() -> None:
    schema = build_schema()
    for key in (
        "$schema",
        "$id",
        "$comment",
        "title",
        "description",
        "type",
        "additionalProperties",
        "properties",
        "definitions",
    ):
        assert key in schema, f"Missing top-level key: {key}"


def test_root_additional_properties_false() -> None:
    schema = build_schema()
    assert schema["additionalProperties"] is False


def test_every_definition_is_a_valid_subschema() -> None:
    """
    Each entry in `definitions` should itself be a valid JSON Schema
    fragment (objects, arrays, refs, etc.).
    """
    schema = build_schema()
    for name, definition in schema["definitions"].items():
        assert isinstance(definition, dict), f"Definition {name!r} is not a dict"


def test_no_dangling_refs() -> None:
    """
    Every $ref in the schema points at an existing entry in definitions.
    """
    schema = build_schema()
    defined_names = set(schema["definitions"].keys())
    dangling = _collect_dangling_refs(schema, defined_names)
    assert not dangling, f"Dangling refs: {sorted(dangling)}"


def _collect_dangling_refs(node: object, defined_names: set[str]) -> set[str]:
    """Walk the schema and return any $ref targets not in defined_names."""
    dangling: set[str] = set()
    if isinstance(node, dict):
        if ref := node.get("$ref"):
            assert ref.startswith("#/definitions/"), f"Unexpected $ref shape: {ref!r}"
            name = ref[len("#/definitions/") :]
            if name not in defined_names:
                dangling.add(name)
        for value in node.values():
            dangling.update(_collect_dangling_refs(value, defined_names))
    elif isinstance(node, list):
        for item in node:
            dangling.update(_collect_dangling_refs(item, defined_names))
    return dangling
