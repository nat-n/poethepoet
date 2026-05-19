"""
SchemaContext — central state for schema generation.

Owns the `$defs` registry, manages `$ref` lifting, and routes per-field
description lookup to the correct source (PoeOptions.description_for_field
for PoeOptions subclasses; extract_field_descriptions directly for
TypedDicts, which don't inherit from PoeOptions).
"""

from __future__ import annotations

# Implementation lands in Task 4.
