"""
SchemaContext — central state for schema generation.

Owns the `$defs` registry, manages `$ref` lifting, and routes per-field
description lookup to the correct source (PoeOptions.description_for_field
for PoeOptions subclasses; extract_field_descriptions directly for
TypedDicts, which don't inherit from PoeOptions).
"""

from __future__ import annotations


class SchemaContext:
    """
    Mutable state shared across a single `build_schema()` invocation.

    Manages the definitions table (lifting reusable shapes to `$defs` and
    handing out `$ref` URIs), routes description lookup to the appropriate
    extractor for the class kind (PoeOptions subclass vs. TypedDict), and
    holds the poe version string used in the generated schema's `$comment`.
    """

    __slots__ = ("_definitions", "version")

    def __init__(self, version: str) -> None:
        self._definitions: dict[str, dict] = {}
        self.version = version

    @property
    def definitions(self) -> dict[str, dict]:
        """
        The accumulated definitions table.

        Returned as a fresh dict to discourage mutation; callers should
        always go through `register`.
        """
        return dict(self._definitions)

    def register(self, name: str, schema: dict) -> str:
        """
        Add `schema` to `$defs` under `name` and return the `$ref` URI.

        Idempotent when called multiple times with the same name AND an
        identical body; raises `ValueError` if a different body is
        registered under an already-used name.
        """
        if name in self._definitions:
            if self._definitions[name] != schema:
                raise ValueError(
                    f"Definition {name!r} already registered with a different "
                    "body; this is a generator bug."
                )
        else:
            self._definitions[name] = schema
        return f"#/definitions/{name}"

    def description_for(self, cls: type, field_name: str) -> str | None:
        """
        Look up the documentation string for a field on `cls`.

        For PoeOptions subclasses, dispatches to PoeOptions.description_for_field
        (which walks the MRO so inherited descriptions resolve). For other
        classes (notably TypedDicts), uses the direct extractor — TypedDicts
        don't have a useful MRO for description inheritance.
        """
        # Local imports keep the schema package decoupled from PoeOptions
        # at module-load time (important for performance — see PoeOptions
        # docs on lazy imports).
        from poethepoet.options import PoeOptions
        from poethepoet.options._docstrings import extract_field_descriptions

        if isinstance(cls, type) and issubclass(cls, PoeOptions):
            return cls.description_for_field(field_name)
        return extract_field_descriptions(cls).get(field_name)  # type: ignore[arg-type]
