"""
JSON Schema generation for poethepoet configuration.

Public API:
    build_schema() -> dict
        Returns the complete draft-07 JSON Schema for the `tool.poe`
        subtable in pyproject.toml.

The package is never imported during normal CLI execution; it is invoked
only by `python -m poethepoet.schema` and by the parity test suite.
"""

from poethepoet.schema.generator import build_schema

__all__ = ["build_schema"]
