"""
Parity: every fixture project's [tool.poe] block validates against the
generated schema. The runtime accepts these (they're used in the rest
of the test suite); the schema must too.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jsonschema import Draft7Validator

# Match the project-wide pattern (tests/conftest.py:21-25) — `tomllib`
# is stdlib only in Python 3.11+, but the project supports 3.10.
try:
    import tomllib as tomli
except ImportError:
    import tomli  # type: ignore[no-redef]

from poethepoet.schema import build_schema


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

# Fixtures whose [tool.poe] configs use experimental or undocumented keys
# that the runtime also rejects when executing tasks (strict=True). The
# fixture project is exploratory/incomplete, not a stable contract, so we
# xfail rather than fix the schema to accept these keys.
#
# Spec §7: JSON Schema can only express the static structure; undocumented
# experimental extensions in fixture projects that the runtime would also
# reject are better tracked here than widened in the schema.
_XFAIL_FIXTURES: dict[str, str] = {
    "conditionals_project/pyproject.toml": (
        "Uses experimental undocumented task keys ('cond', 'prereqs', 'target', "
        "'check') that the runtime also rejects with strict=True. This is an "
        "exploratory fixture for a future feature, not a stable runtime contract."
    ),
}


def _discover_fixture_configs() -> list[tuple[str, Path]]:
    """
    Yield (test_id, config_path) for every config file under fixtures.
    """
    results = []
    for project_dir in sorted(FIXTURES_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        for candidate in ("pyproject.toml", "poe_tasks.toml"):
            config_path = project_dir / candidate
            if config_path.exists():
                test_id = f"{project_dir.name}/{candidate}"
                results.append((test_id, config_path))
    return results


@pytest.fixture(scope="session")
def validator() -> Draft7Validator:
    """
    Session-scoped validator to avoid rebuilding the schema per test.
    """
    return Draft7Validator(build_schema())


def _make_params() -> list[tuple[str, Path] | pytest.param]:
    """
    Build parametrize list, wrapping xfail entries in pytest.param.
    """
    params: list[tuple[str, Path] | pytest.param] = []
    for test_id, config_path in _discover_fixture_configs():
        if reason := _XFAIL_FIXTURES.get(test_id):
            params.append(
                pytest.param(
                    test_id,
                    config_path,
                    marks=pytest.mark.xfail(
                        strict=True,
                        reason=reason,
                    ),
                    id=test_id,
                )
            )
        else:
            params.append(pytest.param(test_id, config_path, id=test_id))
    return params


@pytest.mark.parametrize("test_id, config_path", _make_params())
def test_fixture_config_validates(
    test_id: str, config_path: Path, validator: Draft7Validator
) -> None:
    """
    Load the [tool.poe] block (or root if it's a poe_tasks.toml) and
    validate against the schema.
    """
    raw = config_path.read_bytes()
    data = tomli.loads(raw.decode())

    # Extract the poe-config part.
    if config_path.name == "pyproject.toml":
        poe_config = data.get("tool", {}).get("poe", {})
        if not poe_config:
            pytest.skip(f"{test_id} has no [tool.poe] block")
    else:
        # poe_tasks.toml is the root config directly.
        poe_config = data

    errors = list(validator.iter_errors(poe_config))
    if errors:
        details = "\n".join(
            f"  - {err.message} at path {list(err.path)}" for err in errors
        )
        pytest.fail(
            f"{test_id} failed schema validation:\n{details}\n"
            f"Generated schema may be too strict — review and fix."
        )
