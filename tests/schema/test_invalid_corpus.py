"""
Parity: each curated invalid config in tests/schema/fixtures/invalid/
is rejected by BOTH the full runtime config-load-and-validate pipeline
AND the generated schema. Both validators must reject; otherwise the
schema is too lax.

Each fixture file's first line is `# expected_error: <substring>` —
the runtime's ConfigValidationError message must contain that substring.

The runtime check runs the same flow as ``PoeThePoet._call`` (config
load + ``task_spec.validate``), so it covers both options-level errors
caught by ``PoeOptions.parse`` and task-level errors caught by
``TaskSpec._task_validations`` (e.g. content+option restrictions).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from poethepoet.app import PoeThePoet
from poethepoet.exceptions import ConfigValidationError
from poethepoet.schema import build_schema

# Match the project-wide pattern (tests/conftest.py:21-25) — `tomllib`
# is stdlib only in Python 3.11+, but the project supports 3.10.
try:
    import tomllib as tomli
except ImportError:
    import tomli  # type: ignore[no-redef]

REPO_ROOT = Path(__file__).resolve().parents[2]
INVALID_DIR = REPO_ROOT / "tests" / "schema" / "fixtures" / "invalid"


def _discover_invalid_fixtures() -> list[tuple[str, Path, str]]:
    """
    Return (test_id, path, expected_error_substring) for each fixture.
    """
    results = []
    for fixture in sorted(INVALID_DIR.glob("*.toml")):
        text = fixture.read_text()
        first_line = text.split("\n", 1)[0]
        prefix = "# expected_error:"
        if not first_line.startswith(prefix):
            raise ValueError(
                f"Fixture {fixture.name} is missing the "
                f"{prefix!r} annotation on its first line."
            )
        expected = first_line[len(prefix) :].strip()
        results.append((fixture.stem, fixture, expected))
    return results


def _run_runtime_validation(fixture_path: Path, tmp_path: Path) -> None:
    """
    Mirror PoeThePoet._call's load-and-validate flow against the fixture.
    Raises ConfigValidationError if either config load or
    task_spec.validate rejects the config.
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_bytes(fixture_path.read_bytes())

    poe = PoeThePoet(cwd=tmp_path)

    async def load_and_validate() -> None:
        await poe.config.load(target_path=tmp_path)
        for task_spec in poe.task_specs.load_all():
            task_spec.validate(poe.config, poe.task_specs)

    asyncio.run(load_and_validate())


@pytest.fixture(scope="session")
def validator() -> Draft7Validator:
    """
    Session-scoped validator to avoid rebuilding the schema per test.
    """
    return Draft7Validator(build_schema())


@pytest.mark.parametrize(
    ("test_id", "fixture_path", "expected_error"),
    _discover_invalid_fixtures(),
    ids=[name for name, _, _ in _discover_invalid_fixtures()],
)
def test_invalid_fixture_rejected_by_both_validators(
    test_id: str,
    fixture_path: Path,
    expected_error: str,
    validator: Draft7Validator,
    tmp_path: Path,
) -> None:
    """
    Both runtime and schema must reject the fixture's [tool.poe] block.
    """
    raw = fixture_path.read_bytes()
    data = tomli.loads(raw.decode())
    poe_config = data.get("tool", {}).get("poe", data)

    # 1. Runtime rejects with the expected error substring — via the same
    #    load+validate flow that PoeThePoet runs on real configs.
    with pytest.raises(ConfigValidationError) as runtime_excinfo:
        _run_runtime_validation(fixture_path, tmp_path)
    runtime_message = str(runtime_excinfo.value)
    assert expected_error in runtime_message, (
        f"Runtime error {runtime_message!r} does not contain "
        f"expected substring {expected_error!r}"
    )

    # 2. Schema rejects.
    errors = list(validator.iter_errors(poe_config))
    assert errors, (
        f"Schema accepted {test_id} but runtime rejected it — parity gap. "
        f"Runtime: {runtime_message!r}"
    )
