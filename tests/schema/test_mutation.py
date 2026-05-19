"""
Mutation testing: systematically mutate known-valid seed configs and
assert that the runtime parser and the JSON Schema validator AGREE on
every mutated result (both accept, or both reject).

Disagreements surface as parity bugs: either the schema is too strict
(accepts what runtime rejects) or too lax (accepts what runtime rejects).
Known structural gaps — where the schema validates eagerly and the runtime
validates lazily at task-execution time — are listed in
KNOWN_RUNTIME_ONLY_MISMATCHES and marked xfail(strict=True) so that
obsolete entries surface as XPASS failures.

Spec §7 — Cross-cutting runtime rules that JSON Schema cannot express:
  - deps references to real task names
  - switch control-task type restrictions
  - ref task's "no executor" rule
  - args cross-argument constraints

Runtime lazy validation (not a spec §7 issue, but a structural reality):
  The runtime's ConfigOptions.parse() stores the `tasks` dict as-is and
  defers per-task validation (option parsing, arg parsing, content type
  checking) to task-load / task-execution time. The JSON Schema validates
  all these constraints eagerly. Mismatches of the form
  `schema_accepts=False, runtime_accepts=True` at ConfigOptions.parse()
  level are therefore expected for task-level structural mutations.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator

# Match the project-wide pattern (tests/conftest.py:21-25) — `tomllib`
# is stdlib only in Python 3.11+, but the project supports 3.10.
try:
    import tomllib as tomli
except ImportError:
    import tomli  # type: ignore[no-redef]

from poethepoet.exceptions import ConfigValidationError
from poethepoet.schema import build_schema

REPO_ROOT = Path(__file__).resolve().parents[2]
SEEDS_DIR = REPO_ROOT / "tests" / "schema" / "fixtures" / "seeds"


# ---------------------------------------------------------------------------
# Known runtime-only mismatches.
#
# Each entry is a (seed_name, dot_path, mutator_name) tuple. The value is
# the human-readable reason citing the relevant structural rule.
#
# These entries are applied as pytest.mark.xfail(strict=True): if a listed
# case starts PASSING unexpectedly (schema and runtime agree after a fix),
# the test will fail with XPASS, prompting removal of the stale entry.
#
# "runtime_accepts=True, schema_accepts=False" — schema is correctly
# stricter than the runtime at ConfigOptions.parse() level. The runtime
# would also reject at task-execution level.
#
# "runtime_accepts=False, schema_accepts=True" — schema is too lax; should
# be fixed and the entry removed.
# ---------------------------------------------------------------------------
KNOWN_RUNTIME_ONLY_MISMATCHES: dict[tuple[str, str, str], str] = {
    # --- Group A: task content mutations -----------------------------------
    # Schema validates task shorthand/content types eagerly; runtime defers
    # to task-load time. ConfigOptions.parse stores `tasks` as-is.
    ("simple", "tasks.hello", "replace_str_with_int"): (
        "Runtime stores shorthand task string as-is at parse time; "
        "task content type (string) is only enforced at task-load/execution. "
        "Schema correctly rejects integer shorthand task."
    ),
    ("simple", "tasks.build.cmd", "replace_str_with_int"): (
        "Runtime defers CmdTask content validation to task-load time; "
        "ConfigOptions.parse stores task dict as-is. Schema correctly "
        "rejects integer for cmd content."
    ),
    ("simple", "tasks.build.help", "replace_str_with_int"): (
        "Runtime defers task option validation to task-load time. "
        "Schema correctly rejects integer for help (must be string)."
    ),
    ("executors", "tasks.test.cmd", "replace_str_with_int"): (
        "Runtime defers CmdTask content validation to task-load time. "
        "Schema correctly rejects integer for cmd content."
    ),
    ("complex", "tasks.clean", "replace_str_with_int"): (
        "Runtime stores shorthand task string as-is at parse time. "
        "Schema correctly rejects integer shorthand task."
    ),
    ("complex", "tasks.build.script", "replace_str_with_int"): (
        "Runtime defers ScriptTask content validation to task-load time. "
        "Schema correctly rejects integer for script content."
    ),
    ("complex", "tasks.build.help", "replace_str_with_int"): (
        "Runtime defers task option validation to task-load time. "
        "Schema correctly rejects integer for help (must be string)."
    ),
    ("complex", "tasks.publish.0", "replace_str_with_int"): (
        "Runtime defers sequence task item validation to task-load time. "
        "Schema correctly rejects integer for sequence item (must be string)."
    ),
    ("complex", "tasks.publish.1", "replace_str_with_int"): (
        "Runtime defers sequence task item validation to task-load time. "
        "Schema correctly rejects integer for sequence item (must be string)."
    ),
    ("complex", "tasks.deploy.shell", "replace_str_with_int"): (
        "Runtime defers ShellTask content validation to task-load time. "
        "Schema correctly rejects integer for shell content."
    ),
    ("complex", "tasks.deploy.deps.0", "replace_str_with_int"): (
        "Runtime defers task deps validation to task-load time. "
        "Schema correctly rejects integer in deps list (must be string)."
    ),
    # --- Group B: unexpected keys on task dicts ----------------------------
    # Schema applies additionalProperties:false on task variants; runtime
    # stores task dicts as-is and validates options at task-load time.
    ("simple", "tasks.build", "add_unexpected_key"): (
        "Runtime defers task option validation to task-load time; "
        "additionalProperties on task dicts are only enforced there. "
        "Schema correctly rejects unexpected keys."
    ),
    ("executors", "tasks.test", "add_unexpected_key"): (
        "Runtime defers task option validation to task-load time. "
        "Schema correctly rejects unexpected keys on task dicts."
    ),
    ("complex", "tasks.build", "add_unexpected_key"): (
        "Runtime defers task option validation to task-load time. "
        "Schema correctly rejects unexpected keys on task dicts."
    ),
    ("complex", "tasks.deploy", "add_unexpected_key"): (
        "Runtime defers task option validation to task-load time. "
        "Schema correctly rejects unexpected keys on task dicts."
    ),
    # --- Group C: executor extra keys (runtime generator bug) --------------
    # PoeExecutor.validate_config calls ExecutorOptions.parse() but does not
    # iterate the returned generator, so the validation body never executes.
    # BUG: poethepoet/executor/base.py line 427 — result of parse() is not
    # consumed. Schema correctly rejects extra keys in executor objects.
    ("executors", "executor", "add_unexpected_key"): (
        "Runtime has a generator-not-iterated bug in "
        "PoeExecutor.validate_config (base.py:427): ExecutorOptions.parse() "
        "returns a generator that is never consumed, so extra keys on executor "
        "objects are silently accepted. Schema correctly rejects them."
    ),
}


# ---------------------------------------------------------------------------
# Mutator functions
# ---------------------------------------------------------------------------


def mutator_delete_field(config: dict, path: tuple[str | int, ...]) -> dict | None:
    """
    Delete the value at path. Returns None if path is not deletable
    (e.g. list indices that would leave a hole, or non-existent path).
    """
    result = copy.deepcopy(config)
    target: Any = result
    for key in path[:-1]:
        if isinstance(target, list):
            if not isinstance(key, int) or key >= len(target):
                return None
            target = target[key]
        elif isinstance(target, dict):
            if key not in target:
                return None
            target = target[key]
        else:
            return None
    last = path[-1]
    if isinstance(target, dict):
        if last not in target:
            return None
        del target[last]
    elif isinstance(target, list):
        if not isinstance(last, int) or last >= len(target):
            return None
        del target[last]
    else:
        return None
    return result


def mutator_replace_str_with_int(
    config: dict, path: tuple[str | int, ...]
) -> dict | None:
    """
    Replace the string value at path with the sentinel integer 9999.
    Returns None if the value at path is not a string.
    """
    result = copy.deepcopy(config)
    target: Any = result
    for key in path[:-1]:
        if isinstance(target, (list, dict)):
            target = target[key]
        else:
            return None
    last = path[-1]
    if isinstance(target, (list, dict)):
        current = target[last]
        if not isinstance(current, str):
            return None
        target[last] = 9999
    else:
        return None
    return result


def mutator_add_unexpected_key(
    config: dict, path: tuple[str | int, ...]
) -> dict | None:
    """
    Add an unexpected key to the dict at path. Returns None if the value
    at path is not a dict.
    """
    result = copy.deepcopy(config)
    target: Any = result
    for key in path:
        if isinstance(target, (list, dict)):
            target = target[key]
        else:
            return None
    if not isinstance(target, dict):
        return None
    target["__mutation_unexpected_key__"] = "oops"
    return result


_MUTATORS = {
    "delete_field": mutator_delete_field,
    "replace_str_with_int": mutator_replace_str_with_int,
    "add_unexpected_key": mutator_add_unexpected_key,
}


# ---------------------------------------------------------------------------
# Path enumeration
# ---------------------------------------------------------------------------


def _iter_paths(
    node: Any, current_path: tuple[str | int, ...] = ()
) -> list[tuple[str | int, ...]]:
    """
    Enumerate all node paths in a nested config dict/list. Returns leaf
    paths and intermediate container paths (both are useful for mutations).
    """
    paths: list[tuple[str | int, ...]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = (*current_path, key)
            paths.append(child_path)
            paths.extend(_iter_paths(value, child_path))
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            child_path = (*current_path, idx)
            paths.append(child_path)
            paths.extend(_iter_paths(item, child_path))
    return paths


def _path_to_str(path: tuple[str | int, ...]) -> str:
    """Convert a path tuple to a dot-notation string for display."""
    return ".".join(str(part) for part in path)


# ---------------------------------------------------------------------------
# Seed config loading
# ---------------------------------------------------------------------------


def _load_seed(name: str) -> dict:
    """Load and return the [tool.poe] section of a seed TOML file."""
    path = SEEDS_DIR / f"{name}.toml"
    with path.open("rb") as fh:
        data = tomli.load(fh)
    return data.get("tool", {}).get("poe", {})


_SEED_NAMES = ("simple", "executors", "complex")


# ---------------------------------------------------------------------------
# Parametrize helpers
# ---------------------------------------------------------------------------


def _collect_mutation_cases() -> list[pytest.param]:
    """
    Build the parametrize list for test_mutation_produces_validator_agreement.

    Each case is (seed_name, path_str, mutator_name, mutated_config).
    Cases in KNOWN_RUNTIME_ONLY_MISMATCHES are marked xfail(strict=True).
    """
    cases: list[pytest.param] = []
    for seed_name in _SEED_NAMES:
        seed = _load_seed(seed_name)
        for path in _iter_paths(seed):
            for mutator_name, mutator_fn in _MUTATORS.items():
                mutated = mutator_fn(seed, path)
                if mutated is None:
                    continue  # mutator not applicable at this path
                path_str = _path_to_str(path)
                case_key = (seed_name, path_str, mutator_name)
                test_id = f"{seed_name}::{path_str}::{mutator_name}"

                if reason := KNOWN_RUNTIME_ONLY_MISMATCHES.get(case_key):
                    cases.append(
                        pytest.param(
                            seed_name,
                            path_str,
                            mutator_name,
                            mutated,
                            marks=pytest.mark.xfail(strict=True, reason=reason),
                            id=test_id,
                        )
                    )
                else:
                    cases.append(
                        pytest.param(
                            seed_name,
                            path_str,
                            mutator_name,
                            mutated,
                            id=test_id,
                        )
                    )
    return cases


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def validator() -> Draft7Validator:
    """
    Session-scoped Draft7Validator over the generated schema.
    Built once per test session to avoid rebuilding for every mutation case.
    """
    return Draft7Validator(build_schema())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "seed_name",
    _SEED_NAMES,
    ids=list(_SEED_NAMES),
)
def test_seed_baseline_validates(seed_name: str, validator: Draft7Validator) -> None:
    """
    Sanity check: every seed config is accepted by the schema.
    If a seed fails here, all downstream mutation cases for that seed
    are meaningless.
    """
    seed = _load_seed(seed_name)
    errors = list(validator.iter_errors(seed))
    assert not errors, f"Seed {seed_name!r} failed schema validation:\n" + "\n".join(
        f"  - {err.message} at {list(err.path)}" for err in errors
    )


@pytest.mark.parametrize(
    ("seed_name", "path_str", "mutator_name", "mutated_config"),
    _collect_mutation_cases(),
)
def test_mutation_produces_validator_agreement(
    seed_name: str,
    path_str: str,
    mutator_name: str,
    mutated_config: dict,
    validator: Draft7Validator,
) -> None:
    """
    Apply a single mutation to a seed config and assert that both the
    runtime parser (ConfigOptions.parse) and the JSON Schema validator
    give the same verdict: both accept or both reject.

    A disagreement means one of:
    1. Schema too strict: add an xfail entry to KNOWN_RUNTIME_ONLY_MISMATCHES
       with a reason explaining WHY the runtime is lax (typically: lazy
       validation deferred to task-execution time).
    2. Schema too lax: fix the schema generator/fragment and regenerate.
    """
    from poethepoet.config.partition import ProjectConfig

    # --- Runtime verdict ---
    runtime_accepts = False
    try:
        list(ProjectConfig.ConfigOptions.parse(mutated_config, strict=True))
        runtime_accepts = True
    except (ConfigValidationError, Exception):
        runtime_accepts = False

    # --- Schema verdict ---
    schema_errors = list(validator.iter_errors(mutated_config))
    schema_accepts = len(schema_errors) == 0

    # --- Parity check ---
    assert runtime_accepts == schema_accepts, (
        f"Parity gap for {seed_name!r} :: {path_str!r} :: {mutator_name!r}:\n"
        f"  runtime_accepts = {runtime_accepts}\n"
        f"  schema_accepts  = {schema_accepts}\n"
        + (
            "\n".join(
                f"  schema error: {e.message} at {list(e.path)}" for e in schema_errors
            )
            if not schema_accepts
            else ""
        )
        + "\nIf runtime is lax (lazy validation), add to "
        "KNOWN_RUNTIME_ONLY_MISMATCHES.\n"
        "If schema is lax, fix the schema generator and regenerate."
    )
