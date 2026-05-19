"""
`python -m poethepoet.schema` — regenerate docs/_static/partial-poe.json
from the current PoeOptions definitions.

Phase 3 will add a `poe build-schema` task that wraps this entry point.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from poethepoet.schema import build_schema


def main() -> int:
    """
    Regenerate docs/_static/partial-poe.json from the current state of
    PoeOptions definitions and write it to disk.
    """
    schema = build_schema()
    output_path = Path("docs") / "_static" / "partial-poe.json"

    if not output_path.parent.exists():
        sys.stderr.write(
            f"Target directory {output_path.parent} does not exist. "
            "Run from the repository root.\n"
        )
        return 1

    # Deterministic output: sorted keys, 2-space indent, trailing newline.
    serialized = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    output_path.write_text(serialized)
    sys.stdout.write(f"Wrote {output_path} ({len(serialized)} bytes)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
