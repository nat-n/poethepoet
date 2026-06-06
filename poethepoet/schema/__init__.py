"""
JSON Schema generation for poethepoet configuration.

Public API:
    build_schema() -> dict
        Returns the complete draft-07 JSON Schema for the `tool.poe`
        subtable in pyproject.toml.
    write_schema(output: str) -> int
        Regenerates the schema and writes it to `output`. Invoked by
        the `poe schema-build` task, which fills in the default path
        and wraps this with prettier post-processing.

The package is never imported during normal CLI execution; it is invoked
only by `poe schema-build` and by the parity test suite.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .generator import build_schema

__all__ = ["build_schema", "write_schema"]


def write_schema(output: str) -> int:
    """
    Regenerate the schema from the current PoeOptions definitions and
    write it to `output`.
    """
    schema = build_schema()
    output_path = Path(output)

    if not output_path.parent.exists():
        sys.stderr.write(f"Target directory {output_path.parent} does not exist.\n")
        return 1

    # Deterministic output: sorted keys, 2-space indent, trailing newline.
    serialized = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    output_path.write_text(serialized)
    sys.stdout.write(f"Wrote {output_path} ({len(serialized)} bytes)\n")
    return 0
