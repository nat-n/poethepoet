"""
Tests for the `python -m poethepoet.schema` entry point.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def test_main_writes_partial_poe_json_to_docs(tmp_path: Path) -> None:
    """
    Verifies the CLI writes to docs/_static/partial-poe.json relative
    to the current working directory.
    """
    # Create the target directory structure.
    target_dir = tmp_path / "docs" / "_static"
    target_dir.mkdir(parents=True)

    # Run `python -m poethepoet.schema` with tmp_path as cwd.
    result = subprocess.run(
        [sys.executable, "-m", "poethepoet.schema"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    output_file = target_dir / "partial-poe.json"
    assert output_file.exists()

    # Output is valid JSON, ends with newline.
    content = output_file.read_text()
    assert content.endswith("\n")
    schema = json.loads(content)
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"


def test_main_output_is_deterministic(tmp_path: Path) -> None:
    """
    Running the CLI twice produces byte-identical output. Critical for
    the Phase 3 drift check.
    """
    target_dir = tmp_path / "docs" / "_static"
    target_dir.mkdir(parents=True)

    subprocess.run(
        [sys.executable, "-m", "poethepoet.schema"],
        cwd=tmp_path,
        check=True,
    )
    first = (target_dir / "partial-poe.json").read_bytes()

    subprocess.run(
        [sys.executable, "-m", "poethepoet.schema"],
        cwd=tmp_path,
        check=True,
    )
    second = (target_dir / "partial-poe.json").read_bytes()

    assert first == second
