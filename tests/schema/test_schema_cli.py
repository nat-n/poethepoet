"""
Tests for the `poethepoet.schema.write_schema` entry point and the
`poe schema-build` task that wraps it with prettier post-processing.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from poethepoet.schema import write_schema


def test_write_schema_emits_valid_json_at_output_path(tmp_path: Path) -> None:
    """
    write_schema() writes valid schema JSON to the path it's given.
    """
    output_file = tmp_path / "partial-poe.json"

    assert write_schema(str(output_file)) == 0
    assert output_file.exists()

    content = output_file.read_text()
    assert content.endswith("\n")
    schema = json.loads(content)
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"


def test_write_schema_output_is_deterministic(tmp_path: Path) -> None:
    """
    Calling write_schema() twice produces byte-identical output.
    Underlying invariant the drift check relies on.
    """
    output_file = tmp_path / "partial-poe.json"

    write_schema(str(output_file))
    first = output_file.read_bytes()

    write_schema(str(output_file))
    second = output_file.read_bytes()

    assert first == second


@pytest.mark.schema
@pytest.mark.skipif(
    shutil.which("npx") is None,
    reason="poe schema-build requires Node.js / npx for prettier post-processing",
)
def test_schema_build_task_uses_schemastore_key_order(run_poe) -> None:
    """
    Full `poe schema-build` pipeline (python generator + prettier
    post-process) writes the committed schema with SchemaStore's
    required prettier sort order — `$schema`, `$id`, `$comment` at the
    top of the root object. Runs against the real project root so we
    exercise the task definition contributors actually invoke.
    """
    project_root = Path(__file__).resolve().parents[2]
    result = run_poe("schema-build", cwd=project_root)
    assert result.code == 0, f"schema-build failed:\n{result.capture}\n{result.stderr}"

    lines = (project_root / "docs/_static/partial-poe.json").read_text().splitlines()
    assert lines[0] == "{"
    assert (
        lines[1].lstrip().startswith('"$schema":')
    ), f"Expected first property to be $schema, got: {lines[1]!r}"
    assert (
        lines[2].lstrip().startswith('"$id":')
    ), f"Expected second property to be $id, got: {lines[2]!r}"
    assert (
        lines[3].lstrip().startswith('"$comment":')
    ), f"Expected third property to be $comment, got: {lines[3]!r}"
