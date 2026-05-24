# JSON Schema Generation — Phase 2: Schema Generator and Parity Tests

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate `docs/_static/partial-poe.json` — a draft-07 JSON Schema for the `tool.poe` subtable in `pyproject.toml` — by walking the `PoeOptions` class hierarchy and `PoeTask` / `PoeExecutor` registries already in place from Phase 1, with a parity test suite that ensures the schema accepts/rejects the same configs as the runtime validator.

**Architecture:** A new `poethepoet/schema/` package translates each `TypeAnnotation` to a JSON Schema fragment and assembles per-class fragments (via a `__schema_fragment__` classmethod added to `PoeOptions` and overridden on `PoeTask` and a few task subclasses) into a complete schema. The schema is fully self-contained: shared shapes go into `definitions`; each task variant inlines its full options (Approach B — chosen because draft-07 `additionalProperties: false` doesn't compose correctly through `allOf`). Cross-cutting compositions (task_def union with forward-compat escape hatch, executor tagged union, env value polymorphism, dict-key pattern constraints) live in `fragments.py`. Parity is enforced by four test categories (meta-validation, fixture-config validation, curated invalid corpus, mutation testing).

**Tech Stack:** Python 3.10+, pytest, `jsonschema` (dev-only), stdlib `json` / `ast` / `re`. `tomli` (already a dev dep) for TOML loading in tests — matching the project's existing `try: import tomllib as tomli; except ImportError: import tomli` pattern (Python 3.10 has no stdlib `tomllib`). No new runtime dependencies for end users.

**Spec reference:** `docs/superpowers/specs/2026-05-17-poe-jsonschema-generation-design.md` Sections 2–5 and 7–8.

**Phase 1 reference:** `docs/superpowers/plans/2026-05-17-poe-jsonschema-phase1.md` — the foundations (`Metadata` constraint fields, `description_for_field`, Literal tightening, docstring backfill) that this plan builds on.

**Branching:** Branch from `feature/jsonschema-phase1` so the Phase 2 PR can be stacked on Phase 1 if the latter hasn't merged yet.

**Out of scope for this plan:** the `poe schema-build` task definition, CI drift check, `poe test-schema` task, integration with `poe check`, modification of `poe test-quick`. Those land in Phase 3. **`poe schema-build` is invoked manually in this plan as `python -m poethepoet.schema`** at the point where the initial generated file is committed.

---

## Files touched

**New files (production):**

- `poethepoet/schema/__init__.py` — public API: re-exports `build_schema()` from `generator`.
- `poethepoet/schema/__main__.py` — `python -m poethepoet.schema` entry point; writes `docs/_static/partial-poe.json`.
- `poethepoet/schema/context.py` — `SchemaContext` class (definitions registry, `$ref` lifting, description routing for both `PoeOptions` and TypedDict classes).
- `poethepoet/schema/translate.py` — `translate_type(annotation, ctx) -> dict` and supporting per-annotation-class translators.
- `poethepoet/schema/fragments.py` — cross-cutting composition: `task_def_schema`, `executor_option_schema`, `env_option_schema`, `envfile_option_schema`, `tasks_map_schema`, `groups_map_schema`, name-pattern imports.
- `poethepoet/schema/generator.py` — `build_schema()`: orchestrates walks, hook calls, and definitions assembly into the root schema.
- `docs/_static/partial-poe.json` — generated output, committed to repo.

**New files (tests):**

- `tests/schema/conftest.py` — session-scoped `built_schema` and `validator` fixtures; auto-applies `pytest.mark.schema` to parity-test files only.
- `tests/schema/test_translate.py` — unit tests for the type translator (NOT marked `schema`; runs in default `poe test`).
- `tests/schema/test_context.py` — unit tests for `SchemaContext` (NOT marked).
- `tests/schema/test_schema_fragment.py` — unit tests for the `__schema_fragment__` default + per-class overrides (NOT marked).
- `tests/schema/test_meta.py` — meta-validation of the generated schema (MARKED `schema`).
- `tests/schema/test_fixture_configs.py` — every `tests/fixtures/*_project` config validates (MARKED).
- `tests/schema/test_invalid_corpus.py` — curated invalid configs rejected by both validators (MARKED).
- `tests/schema/test_mutation.py` — mutation testing of valid seeds (MARKED).
- `tests/schema/fixtures/invalid/*.toml` — curated invalid configs with `# expected_error:` annotations.
- `tests/schema/fixtures/seeds/*.toml` — valid configs used as mutation starting points.

**Modified files:**

- `poethepoet/config/partition.py` — lift group-name regex to a module-level `_GROUP_NAME_PATTERN` constant so `fragments.py` can import it.
- `poethepoet/options/base.py` — add `PoeOptions.__schema_fragment__` classmethod (default implementation).
- `poethepoet/task/base.py` — add `PoeTask.__schema_fragment__` override (wraps `TaskOptions` shape with discriminator key + content schema).
- `poethepoet/task/switch.py` — override `__schema_fragment__` for the case-item content structure.
- `poethepoet/task/sequence.py` — override `__schema_fragment__` for recursive `task_def` items.
- `poethepoet/task/parallel.py` — same override as sequence.
- `poethepoet/task/args.py` — override `ArgSpec.__schema_fragment__` for per-arg shape; orchestrator handles outer list-vs-dict polymorphism.
- `pyproject.toml` — register `schema` pytest marker; add `jsonschema` to dev dependencies.

---

## Task 1: Unify task/group name regexes as single sources of truth

**Files:**

- Modify: `poethepoet/config/partition.py` (lift inline group-name regex to module-level constant)
- Modify: `poethepoet/task/base.py` (consolidate `_TASK_NAME_PATTERN` to encompass the first-char rule currently checked separately at line 319)

**Why:** Phase 2's orchestrator needs to emit `patternProperties` for the `tasks` and `groups` maps. The schema patterns must come from a single source of truth — if the runtime check changes, the schema should automatically follow.

Two related fixes:

1. **Group name pattern:** currently inline at `ProjectConfig.ConfigOptions.validate`; lift to module-level `_GROUP_NAME_PATTERN` so `fragments.py` can import it.
2. **Task name pattern:** currently `_TASK_NAME_PATTERN = re.compile(r"^\w[\w\d\-\_\+\:]*$")` at `task/base.py:26`, plus a separate `if not (self.name[0].isalpha() or self.name[0] == "_"):` first-char check at `task/base.py:319`. The schema's `patternProperties` needs the _combined_ rule — letter or underscore first, followed by word chars / dash / colon / plus. Consolidate into one regex: `r"^[A-Za-z_][\w\-:+]*$"` and remove the redundant runtime check.

**Behavior change note:** the unified task-name regex uses ASCII `[A-Za-z_]` for the first char rather than the Unicode-aware `.isalpha()`. The existing runtime accepts Unicode letters as the first char (e.g. `αlpha_task`); the new rule rejects them. This is a deliberate tightening — JSON Schema regex implementations across editors handle Unicode `\w`/`\W` inconsistently, and ASCII-only task names are the de facto convention. Worth flagging in the commit message.

- [ ] **Step 1: Locate the current group-name validation and task-name check**

Run: `grep -n 'group_name\|_TASK_NAME_PATTERN\|isalpha' poethepoet/config/partition.py poethepoet/task/base.py | head -20`

You should see:

- `poethepoet/task/base.py:26: _TASK_NAME_PATTERN = re.compile(r"^\w[\w\d\-\_\+\:]*$")`
- `poethepoet/task/base.py:319: if not (self.name[0].isalpha() or self.name[0] == "_"):`
- The inline `re.fullmatch(r"[\w\-_]+", group_name)` somewhere in `partition.py`'s `ProjectConfig.ConfigOptions.validate`

- [ ] **Step 2: Write failing tests for both constants**

Append to `tests/options/test_options.py`:

```python
def test_group_name_pattern_constant_exposed() -> None:
    """
    The group name pattern is module-level so external consumers (e.g. the
    Phase 2 schema generator) can import it as the single source of truth.
    """
    from poethepoet.config.partition import _GROUP_NAME_PATTERN

    assert _GROUP_NAME_PATTERN.fullmatch("my_group")
    assert _GROUP_NAME_PATTERN.fullmatch("my-group")
    assert _GROUP_NAME_PATTERN.fullmatch("group123")
    assert not _GROUP_NAME_PATTERN.fullmatch("bad group")  # space rejected
    assert not _GROUP_NAME_PATTERN.fullmatch("")  # empty rejected


def test_task_name_pattern_unified_encompasses_first_char_rule() -> None:
    """
    The unified _TASK_NAME_PATTERN enforces "letter or underscore first"
    directly in the regex — no separate runtime check needed.
    """
    from poethepoet.task.base import _TASK_NAME_PATTERN

    # Letter or underscore first: accepted.
    assert _TASK_NAME_PATTERN.fullmatch("hello")
    assert _TASK_NAME_PATTERN.fullmatch("_private")
    assert _TASK_NAME_PATTERN.fullmatch("Task-1")
    assert _TASK_NAME_PATTERN.fullmatch("name:with:colons")
    assert _TASK_NAME_PATTERN.fullmatch("with+plus")

    # Digit first: rejected by the regex itself (no separate check needed).
    assert not _TASK_NAME_PATTERN.fullmatch("1bad")
    # Punctuation / whitespace first: rejected.
    assert not _TASK_NAME_PATTERN.fullmatch("-bad")
    assert not _TASK_NAME_PATTERN.fullmatch(" bad")
    # Empty: rejected.
    assert not _TASK_NAME_PATTERN.fullmatch("")


def test_runtime_still_rejects_invalid_task_names_via_unified_pattern() -> None:
    """
    After consolidation, the runtime continues to reject invalid task
    names — just through the unified regex rather than a separate
    isalpha() check.
    """
    from poethepoet.config import PoeConfig
    from poethepoet.exceptions import ConfigValidationError
    from poethepoet.task.base import TaskSpecFactory

    config = PoeConfig(
        table={"tasks": {"1bad_name": {"cmd": "echo hi"}}},
    )
    factory = TaskSpecFactory(config)
    factory.load_all()

    spec = next(iter(factory))
    with pytest.raises(ConfigValidationError):
        spec.validate(config, factory)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `poe test tests/options/test_options.py -k "group_name_pattern or task_name_pattern or runtime_still_rejects"`

Expected:

- `test_group_name_pattern_constant_exposed`: ImportError (constant doesn't exist yet).
- `test_task_name_pattern_unified_encompasses_first_char_rule`: PASS or FAIL — the current regex `^\w[\w\d\-\_\+\:]*$` allows digit-first (`\w` includes digits), so `_TASK_NAME_PATTERN.fullmatch("1bad")` returns a match → assertion fails.
- `test_runtime_still_rejects_invalid_task_names_via_unified_pattern`: PASS (current behavior already rejects via the line 319 check).

- [ ] **Step 4: Define `_GROUP_NAME_PATTERN`**

In `poethepoet/config/partition.py`, near the top of the file (after the imports, before `KNOWN_SHELL_INTERPRETERS`), add:

```python
_GROUP_NAME_PATTERN = re.compile(r"^[\w\-_]+$")
"""
Pattern for valid group names. Used by ProjectConfig.ConfigOptions.validate
and (in Phase 2) by the schema generator's groups_map patternProperties.
"""
```

Note the `^...$` anchors — the existing inline regex used `re.fullmatch` without anchors, which is equivalent for `fullmatch` but the explicit anchors mean `re.match` also works. The schema's `patternProperties` requires the anchored form anyway.

Then locate the inline `re.fullmatch(r"[\w\-_]+", group_name)` call inside `ProjectConfig.ConfigOptions.validate` and replace it with `_GROUP_NAME_PATTERN.fullmatch(group_name)`. The surrounding error message stays unchanged.

- [ ] **Step 5: Unify `_TASK_NAME_PATTERN`**

In `poethepoet/task/base.py`, replace line 26:

```python
_TASK_NAME_PATTERN = re.compile(r"^\w[\w\d\-\_\+\:]*$")
```

with:

```python
_TASK_NAME_PATTERN = re.compile(r"^[A-Za-z_][\w\-:+]*$")
"""
Pattern for valid task names: must start with an ASCII letter or
underscore, followed by any combination of word chars, hyphen, colon,
or plus. Used by both runtime validation and the schema generator's
tasks_map patternProperties.

Note: the previous pattern was Unicode-aware via `\w` for the first
char, combined with a separate `.isalpha()` runtime check. The unified
form is ASCII-only — see commit message for rationale.
"""
```

Then in `_base_validations` (around line 319), **delete** the now-redundant first-char check:

```python
# DELETE these lines (they're now covered by _TASK_NAME_PATTERN):
if not (self.name[0].isalpha() or self.name[0] == "_"):
    raise ConfigValidationError(
        "Task names must start with a letter or underscore."
    )
```

The remaining check at line 324 (`_TASK_NAME_PATTERN.match(self.name)`) covers both rules now. Adjust the error message there if needed to reflect the combined rule:

```python
if not self.parent and not _TASK_NAME_PATTERN.match(self.name):
    raise ConfigValidationError(
        "Task names must start with a letter or underscore and contain "
        "only alphanumeric characters, colon, underscore, dash, or plus."
    )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `poe test tests/options/test_options.py -k "group_name_pattern or task_name_pattern or runtime_still_rejects"`

Expected: All three PASS.

- [ ] **Step 7: Run the full test suite to verify no regression**

Run: `poe test`

Expected: PASS. If any test relied on Unicode-first task names (extremely unlikely), it would surface here.

- [ ] **Step 8: Commit**

```bash
git add poethepoet/config/partition.py poethepoet/task/base.py tests/options/test_options.py
git commit -m "$(cat <<'EOF'
refactor: unify task/group name patterns as single sources of truth

Two related changes:
- Lift the inline group-name regex in ProjectConfig.ConfigOptions.validate
  to a module-level _GROUP_NAME_PATTERN constant.
- Consolidate _TASK_NAME_PATTERN to encompass the first-char rule
  previously enforced by a separate isalpha() check. The new regex
  ^[A-Za-z_][\w\-:+]*$ tightens first-char acceptance from Unicode
  letters to ASCII letters (deliberate; matches JSON Schema regex
  portability and de facto task naming conventions).

Phase 2 prep: the schema generator's tasks_map and groups_map
patternProperties import these constants directly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add `jsonschema` dev dependency and register the `schema` pytest marker

**Files:**

- Modify: `pyproject.toml`

**Why:** The parity tests need a JSON Schema validator (`jsonschema.Draft7Validator`). End users never see this dependency — it's dev-only. Registering the `schema` marker silences pytest's "unknown marker" warning when we use it later.

- [ ] **Step 1: Inspect the current pyproject.toml structure**

Run: `grep -n 'jsonschema\|\[tool.poetry\|tool.uv\|pytest\|markers' pyproject.toml | head -30`

Identify where dev dependencies live and where pytest config lives.

- [ ] **Step 2: Add `jsonschema` to dev dependencies**

Add `jsonschema = "^4.0"` (or the equivalent line for whatever build tool this project uses — check the existing entries to match style) to the dev dependency group.

- [ ] **Step 3: Register the `schema` pytest marker**

Locate `[tool.pytest.ini_options]` in `pyproject.toml`. If the `markers` key exists, append to it; otherwise add it. The final state should include:

```toml
[tool.pytest.ini_options]
markers = [
    # ... existing markers ...
    "schema: schema validation tests (slow; require jsonschema; auto-applied to parity tests in tests/schema/)",
]
```

(Preserve any existing markers verbatim.)

- [ ] **Step 4: Refresh the lockfile**

Run the project's lockfile-refresh command (typically `poetry lock --no-update` or `uv lock`).

- [ ] **Step 5: Install the new dev dependency**

Run the project's install command (typically `poetry install` or `uv sync`).

- [ ] **Step 6: Verify jsonschema is importable**

Run: `python -c "from jsonschema import Draft7Validator; print(Draft7Validator.__name__)"`

Expected: `Draft7Validator`.

- [ ] **Step 7: Verify the marker is registered (no warning when used)**

Run: `python -c "
import pytest
import subprocess
result = subprocess.run(['pytest', '--markers'], capture_output=True, text=True)
print('schema marker present' if '@pytest.mark.schema' in result.stdout else 'MISSING')
"`

Expected: `schema marker present`.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml poetry.lock uv.lock 2>/dev/null || true  # whichever lockfile exists
git commit -m "$(cat <<'EOF'
chore: add jsonschema dev dependency and register schema pytest marker

Foundations for the Phase 2 parity test suite. Phase 3 will add a
poe test-schema task that runs only marker-selected tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Create the schema package skeleton and tests directory

**Files:**

- Create: `poethepoet/schema/__init__.py`
- Create: `poethepoet/schema/context.py`
- Create: `poethepoet/schema/translate.py`
- Create: `poethepoet/schema/fragments.py`
- Create: `poethepoet/schema/generator.py`
- Create: `poethepoet/schema/__main__.py`
- Create: `tests/schema/conftest.py`

**Why:** Establish the file layout so subsequent tasks have stable import targets. Use placeholder content that will be replaced as features land. The conftest auto-marks parity-test files now so we don't add the marker decoration to every parity test file individually later.

- [ ] **Step 1: Write a failing smoke-import test**

Create `tests/schema/test_smoke.py`:

```python
"""
Phase 2 smoke test — verifies the schema package layout is importable.
This file is intentionally not marked `schema` (it's a fast smoke check).
"""


def test_package_imports() -> None:
    from poethepoet.schema import build_schema

    assert callable(build_schema)


def test_package_submodules_importable() -> None:
    # These are the submodules subsequent tasks will populate.
    import poethepoet.schema.context  # noqa: F401
    import poethepoet.schema.fragments  # noqa: F401
    import poethepoet.schema.generator  # noqa: F401
    import poethepoet.schema.translate  # noqa: F401
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `poe test tests/schema/test_smoke.py`

Expected: ImportError (the package doesn't exist yet).

- [ ] **Step 3: Create the package skeleton**

Create `poethepoet/schema/__init__.py`:

```python
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
```

Create `poethepoet/schema/context.py`:

```python
"""
SchemaContext — central state for schema generation.

Owns the `$defs` registry, manages `$ref` lifting, and routes per-field
description lookup to the correct source (PoeOptions.description_for_field
for PoeOptions subclasses; extract_field_descriptions directly for
TypedDicts, which don't inherit from PoeOptions).
"""

from __future__ import annotations

# Implementation lands in Task 4.
```

Create `poethepoet/schema/translate.py`:

```python
"""
TypeAnnotation → JSON Schema translation.

Each `TypeAnnotation` subclass is translated by a corresponding function.
The translator does not know about poe domain shapes (tasks, executors,
etc.); it only emits the structural JSON Schema corresponding to a type
annotation. Cross-cutting compositions live in `fragments.py`.
"""

from __future__ import annotations

# Implementation lands in Tasks 5–7.
```

Create `poethepoet/schema/fragments.py`:

```python
"""
Cross-cutting JSON Schema fragments that aren't owned by any single
PoeOptions class — the task_def union (incl. forward-compat fallback),
the executor tagged union, env/envfile value polymorphism, and the
patternProperties for the tasks/groups maps.
"""

from __future__ import annotations

# Implementation lands in Tasks 13–16.
```

Create `poethepoet/schema/generator.py`:

```python
"""
Orchestrator: walks ProjectConfig.ConfigOptions and the PoeTask /
PoeExecutor registries, calls __schema_fragment__ hooks, and assembles
the complete root schema.
"""

from __future__ import annotations


def build_schema() -> dict:
    """
    Build the complete JSON Schema for the `tool.poe` subtable.

    Returns a self-contained draft-07 schema as a dict. Stable across
    runs (deterministic key order) so committed output diffs cleanly.
    """
    # Placeholder until Task 17 lands.
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "https://json.schemastore.org/partial-poe.json",
        "type": "object",
    }
```

Create `poethepoet/schema/__main__.py`:

```python
"""
`python -m poethepoet.schema` — regenerate docs/_static/partial-poe.json.

Phase 3 will add a `poe schema-build` task that wraps this entry point.
"""

from __future__ import annotations

# Implementation lands in Task 18.


if __name__ == "__main__":
    raise SystemExit("Not yet implemented — see Task 18")
```

- [ ] **Step 4: Create the tests/schema/ conftest with auto-marking**

Create `tests/schema/conftest.py`:

```python
"""
Auto-applies `pytest.mark.schema` to the parity-test files in this
directory. Other tests under tests/schema/ (unit tests for the
translator, context, and __schema_fragment__ hook) are NOT auto-marked,
so they continue to run under the default `poe test` invocation.
"""

import pytest

# Filenames containing parity tests (slow, require the full schema build).
# Phase 3 will configure `poe test-quick` to exclude the `schema` marker.
_PARITY_TEST_FILES = frozenset(
    {
        "test_meta.py",
        "test_fixture_configs.py",
        "test_invalid_corpus.py",
        "test_mutation.py",
    }
)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """
    Apply the `schema` marker to parity-test items based on filename.
    """
    for item in items:
        if item.fspath.basename in _PARITY_TEST_FILES:
            item.add_marker(pytest.mark.schema)
```

- [ ] **Step 5: Run the smoke test to verify it passes**

Run: `poe test tests/schema/test_smoke.py`

Expected: PASS — `build_schema` is importable and callable; submodules are importable.

- [ ] **Step 6: Verify the conftest doesn't apply the marker to the smoke test**

Run: `poe test tests/schema/test_smoke.py -m 'not schema'`

Expected: PASS, tests run (i.e. they were NOT marked schema).

Run: `poe test tests/schema/test_smoke.py -m schema`

Expected: 0 tests selected (smoke tests are not parity tests).

- [ ] **Step 7: Commit**

```bash
git add poethepoet/schema/ tests/schema/conftest.py tests/schema/test_smoke.py
git commit -m "$(cat <<'EOF'
feat: scaffold poethepoet.schema package and tests/schema/ layout

Empty skeleton — each module gets implemented in subsequent tasks.
The tests/schema/ conftest auto-applies pytest.mark.schema to parity
test files only, so unit tests of translator/hook code continue to
run under `poe test` while the slow parity suite gates behind a
dedicated marker.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Implement `SchemaContext`

**Files:**

- Modify: `poethepoet/schema/context.py`
- Create: `tests/schema/test_context.py`

**Why:** Subsequent tasks (translator, fragment hooks, orchestrator) need a shared object that owns:

1. The `definitions` registry: `register(name: str, schema: dict) -> str` returning the `$ref` URI.
2. Description routing: `description_for(cls: type, field_name: str) -> str | None` that dispatches to `PoeOptions.description_for_field` (which walks MRO) for `PoeOptions` subclasses, and to `extract_field_descriptions` directly for TypedDict classes (which have no MRO walk needed).
3. The poe `__version__` string for the `$comment` line.

The context is constructed once per `build_schema()` call.

- [ ] **Step 1: Write failing tests for the context**

Create `tests/schema/test_context.py`:

```python
"""
Unit tests for SchemaContext.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from poethepoet.options import PoeOptions
from poethepoet.options.annotations import Metadata, option_annotation
from poethepoet.schema.context import SchemaContext


class _Sample(PoeOptions):
    foo: str = ""
    """The foo field — described here."""


@option_annotation
class _SampleTypedDict(TypedDict):
    bar: str
    """The bar field on the TypedDict."""


def test_register_returns_ref_string() -> None:
    ctx = SchemaContext(version="0.46.0")
    ref = ctx.register("my_thing", {"type": "object"})
    assert ref == "#/definitions/my_thing"


def test_register_stores_definition() -> None:
    ctx = SchemaContext(version="0.46.0")
    ctx.register("my_thing", {"type": "object"})
    assert ctx.definitions == {"my_thing": {"type": "object"}}


def test_register_rejects_duplicate_name_with_different_body() -> None:
    ctx = SchemaContext(version="0.46.0")
    ctx.register("name", {"type": "string"})
    import pytest
    with pytest.raises(ValueError, match="already registered"):
        ctx.register("name", {"type": "integer"})


def test_register_idempotent_for_identical_body() -> None:
    ctx = SchemaContext(version="0.46.0")
    ref1 = ctx.register("name", {"type": "string"})
    ref2 = ctx.register("name", {"type": "string"})
    assert ref1 == ref2
    assert ctx.definitions == {"name": {"type": "string"}}


def test_description_for_poeoptions_uses_mro_aware_helper() -> None:
    ctx = SchemaContext(version="0.46.0")
    assert (
        ctx.description_for(_Sample, "foo")
        == "The foo field — described here."
    )


def test_description_for_typeddict_uses_direct_extraction() -> None:
    ctx = SchemaContext(version="0.46.0")
    assert (
        ctx.description_for(_SampleTypedDict, "bar")
        == "The bar field on the TypedDict."
    )


def test_description_returns_none_for_missing_field() -> None:
    ctx = SchemaContext(version="0.46.0")
    assert ctx.description_for(_Sample, "nonexistent") is None


def test_version_stored_for_comment_line() -> None:
    ctx = SchemaContext(version="0.46.0")
    assert ctx.version == "0.46.0"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `poe test tests/schema/test_context.py`

Expected: All tests FAIL — `SchemaContext` is not yet defined.

- [ ] **Step 3: Implement `SchemaContext`**

Replace the contents of `poethepoet/schema/context.py` with:

```python
"""
SchemaContext — central state for schema generation.

Owns the `$defs` registry, manages `$ref` lifting, and routes per-field
description lookup to the correct source (PoeOptions.description_for_field
for PoeOptions subclasses; extract_field_descriptions directly for
TypedDicts, which don't inherit from PoeOptions).
"""

from __future__ import annotations

from typing import Any


class SchemaContext:
    """
    Mutable state shared across a single `build_schema()` invocation.

    Manages the definitions table (lifting reusable shapes to `$defs` and
    handing out `$ref` URIs), routes description lookup to the appropriate
    extractor for the class kind (PoeOptions subclass vs. TypedDict), and
    holds the poe version string used in the generated schema's `$comment`.
    """

    __slots__ = ("_definitions", "version")

    def __init__(self, version: str):
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
        return extract_field_descriptions(cls).get(field_name)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poe test tests/schema/test_context.py`

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add poethepoet/schema/context.py tests/schema/test_context.py
git commit -m "$(cat <<'EOF'
feat: implement SchemaContext for schema generation

Owns the $defs registry, dispatches description lookup correctly for
both PoeOptions (MRO-aware) and TypedDict (direct extraction) sources,
and holds the poe version string for the schema's $comment.

Resolves the "TypedDict vs. PoeOptions emission paths can diverge" risk
called out in the spec (Section 7) by routing both through one helper.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Translate `PrimitiveType`, `LiteralType`, `AnyType`, `NoneType`

**Files:**

- Modify: `poethepoet/schema/translate.py`
- Create: `tests/schema/test_translate.py`

**Why:** These are the leaf type annotations — no recursion needed. Implementing them first gives later tasks (lists, dicts, unions) a base case.

The translator reads internal attributes of TypeAnnotation subclasses (`_annotation`, `_values`, `_metadata`). This is intentional and documented coupling: the translator is a privileged consumer of the TypeAnnotation hierarchy, just like `validate()` is. Mark this with a clear comment.

- [ ] **Step 1: Write failing tests for primitives, literals, and any/none**

Create `tests/schema/test_translate.py`:

```python
"""
Unit tests for the TypeAnnotation → JSON Schema translator.

Each translator is tested in isolation. Cross-cutting compositions
(unions of multiple variants, tagged unions over the `type:` key) live
in tests/schema/test_schema_fragment.py and tests/schema/test_meta.py.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

import pytest

from poethepoet.options.annotations import Metadata, TypeAnnotation
from poethepoet.schema.context import SchemaContext
from poethepoet.schema.translate import translate_type


@pytest.fixture
def ctx() -> SchemaContext:
    return SchemaContext(version="0.0.0")


# --- PrimitiveType ---

def test_str_to_string_schema(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(str)
    assert translate_type(annotation, ctx) == {"type": "string"}


def test_int_to_integer_schema(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(int)
    assert translate_type(annotation, ctx) == {"type": "integer"}


def test_float_to_number_schema(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(float)
    assert translate_type(annotation, ctx) == {"type": "number"}


def test_bool_to_boolean_schema(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(bool)
    assert translate_type(annotation, ctx) == {"type": "boolean"}


# --- Metadata-driven constraints on primitives ---

def test_str_with_pattern(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(
        Annotated[str, Metadata(pattern=r"^[a-z]+$")]
    )
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "string", "pattern": "^[a-z]+$"}


def test_str_with_min_max_length(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(
        Annotated[str, Metadata(min_length=1, max_length=50)]
    )
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "string", "minLength": 1, "maxLength": 50}


def test_int_with_minimum_maximum(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(
        Annotated[int, Metadata(minimum=-2, maximum=2)]
    )
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "integer", "minimum": -2, "maximum": 2}


def test_int_with_zero_minimum_not_dropped(ctx: SchemaContext) -> None:
    """
    Guards against the falsy-value regression that Phase 1 fixed in
    metadata_get; minimum=0 must appear in the output.
    """
    annotation = TypeAnnotation.parse(
        Annotated[int, Metadata(minimum=0)]
    )
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "integer", "minimum": 0}


def test_str_with_examples(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(
        Annotated[str, Metadata(examples=["foo", "bar"])]
    )
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "string", "examples": ["foo", "bar"]}


# --- LiteralType ---

def test_string_literal_to_enum(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(Literal["a", "b", "c"])
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "string", "enum": ["a", "b", "c"]}


def test_int_literal_to_enum(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(Literal[1, 2, 3])
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "integer", "enum": [1, 2, 3]}


def test_mixed_literal_drops_type_field(ctx: SchemaContext) -> None:
    """
    When literal values span multiple JSON types, only emit `enum`
    (no `type:`).
    """
    annotation = TypeAnnotation.parse(Literal[True, "yes"])
    schema = translate_type(annotation, ctx)
    assert schema == {"enum": [True, "yes"]}


# --- AnyType ---

def test_any_to_empty_schema(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(Any)
    assert translate_type(annotation, ctx) == {}


# --- NoneType ---

def test_none_translates_to_null_schema(ctx: SchemaContext) -> None:
    """
    NoneType isn't usually emitted standalone (Optional collapse happens
    at the UnionType level), but the translator should still produce a
    valid schema for it for completeness.
    """
    annotation = TypeAnnotation.parse(None)
    assert translate_type(annotation, ctx) == {"type": "null"}


# --- ShellInterpreter alias (smoke test) ---

def test_shell_interpreter_literal_alias_translates(ctx: SchemaContext) -> None:
    """
    Verifies the register_type_alias mechanism from Phase 1 works
    end-to-end: ShellInterpreter is a registered alias for a Literal,
    and translation should produce the expected enum schema.
    """
    from poethepoet.config.partition import ShellInterpreter

    annotation = TypeAnnotation.parse(ShellInterpreter)
    schema = translate_type(annotation, ctx)
    assert schema["type"] == "string"
    assert set(schema["enum"]) == {
        "posix", "sh", "bash", "zsh", "fish", "pwsh", "powershell", "python",
    }
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `poe test tests/schema/test_translate.py`

Expected: All tests FAIL — `translate_type` not yet defined.

- [ ] **Step 3: Implement the leaf translators**

Replace the contents of `poethepoet/schema/translate.py` with:

```python
"""
TypeAnnotation → JSON Schema translation.

Each TypeAnnotation subclass is translated by a dedicated function.
Translators access internal attributes of TypeAnnotation subclasses
(`_annotation`, `_values`, etc.) — this is intentional coupling: the
translator is a privileged consumer of the TypeAnnotation hierarchy,
on the same footing as `validate()` and `zero_value()`.
"""

from __future__ import annotations

from typing import Any

from poethepoet.options.annotations import (
    AnyType,
    LiteralType,
    NoneType,
    PrimitiveType,
    TypeAnnotation,
)

# Mapping from Python primitive types to JSON Schema `type:` strings.
_PRIMITIVE_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def translate_type(annotation: TypeAnnotation, ctx) -> dict:
    """
    Translate a TypeAnnotation into a JSON Schema fragment (a dict).

    The translator does NOT mutate `ctx.definitions` itself; that's the
    schema-fragment hook's responsibility. The `ctx` parameter is passed
    through so future translators (e.g. recursive references) can lift
    definitions when needed.
    """
    if isinstance(annotation, PrimitiveType):
        return _translate_primitive(annotation)
    if isinstance(annotation, LiteralType):
        return _translate_literal(annotation)
    if isinstance(annotation, AnyType):
        return {}
    if isinstance(annotation, NoneType):
        return {"type": "null"}
    raise NotImplementedError(
        f"No translator yet for {type(annotation).__name__} (annotation: "
        f"{annotation!r})"
    )


def _translate_primitive(annotation: PrimitiveType) -> dict:
    """Translate str/int/float/bool with Metadata-driven constraints."""
    py_type = annotation._annotation
    schema: dict[str, Any] = {"type": _PRIMITIVE_TYPE_MAP[py_type]}

    # Layer in constraint metadata. Each is `None` if unset (the
    # Phase 1 metadata_get bug fix ensures explicitly-zero values
    # like minimum=0 are NOT silently dropped here).
    if py_type is str:
        if (pattern := annotation.metadata_get("pattern")) is not None:
            schema["pattern"] = pattern
        if (min_length := annotation.metadata_get("min_length")) is not None:
            schema["minLength"] = min_length
        if (max_length := annotation.metadata_get("max_length")) is not None:
            schema["maxLength"] = max_length

    if py_type in (int, float):
        if (minimum := annotation.metadata_get("minimum")) is not None:
            schema["minimum"] = minimum
        if (maximum := annotation.metadata_get("maximum")) is not None:
            schema["maximum"] = maximum

    if (examples := annotation.metadata_get("examples")) is not None:
        schema["examples"] = examples

    return schema


def _translate_literal(annotation: LiteralType) -> dict:
    """
    Translate a Literal type. Emit `{type: <shared>, enum: [...]}` when
    all literal values are the same JSON-typed; emit just `{enum: [...]}`
    when they span types.
    """
    values = list(annotation._values)
    types = {_python_value_to_json_type(value) for value in values}
    if len(types) == 1 and (only := next(iter(types))) is not None:
        return {"type": only, "enum": values}
    return {"enum": values}


def _python_value_to_json_type(value: Any) -> str | None:
    """Map a literal value to the corresponding JSON Schema `type:` string."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poe test tests/schema/test_translate.py`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add poethepoet/schema/translate.py tests/schema/test_translate.py
git commit -m "$(cat <<'EOF'
feat: translate primitives, literals, any, and none to JSON Schema

Leaf-level translators with Metadata-driven constraint emission.
Includes a regression guard for the falsy-value case (minimum=0
must appear in the output) and a smoke test confirming that the
ShellInterpreter Literal type alias from Phase 1 resolves cleanly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Translate `ListType`, `DictType`, `TypedDictType`

**Files:**

- Modify: `poethepoet/schema/translate.py`
- Modify: `tests/schema/test_translate.py`

**Why:** Collections need recursion into their value/element type. TypedDict translation needs description routing through the SchemaContext (the consequential fix for the spec's Section 7 risk).

- [ ] **Step 1: Add failing tests for collection translators**

Append to `tests/schema/test_translate.py`:

```python
# --- ListType ---

def test_list_of_str_to_array_schema(ctx: SchemaContext) -> None:
    from collections.abc import Sequence
    annotation = TypeAnnotation.parse(Sequence[str])
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "array", "items": {"type": "string"}}


def test_list_with_min_max_items(ctx: SchemaContext) -> None:
    from collections.abc import Sequence
    annotation = TypeAnnotation.parse(
        Annotated[Sequence[str], Metadata(min_length=1, max_length=10)]
    )
    schema = translate_type(annotation, ctx)
    assert schema == {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 1,
        "maxItems": 10,
    }


def test_untyped_list_to_unconstrained_array(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(list)
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "array"}


# --- DictType ---

def test_dict_str_to_str_schema(ctx: SchemaContext) -> None:
    from collections.abc import Mapping
    annotation = TypeAnnotation.parse(Mapping[str, str])
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "object", "additionalProperties": {"type": "string"}}


def test_untyped_dict_to_unconstrained_object(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(dict)
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "object"}


# --- TypedDictType ---

def test_typeddict_emits_properties_and_required(ctx: SchemaContext) -> None:
    from typing import TypedDict
    from poethepoet.options.annotations import option_annotation

    @option_annotation
    class _ExampleTD(TypedDict):
        name: str
        """The name."""

        count: int

    _ExampleTD.__optional_keys__ = frozenset()  # all required

    annotation = TypeAnnotation.parse(_ExampleTD)
    schema = translate_type(annotation, ctx)

    # Properties and required keys
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["name"] == {
        "type": "string", "description": "The name.",
    }
    assert schema["properties"]["count"] == {"type": "integer"}
    assert sorted(schema["required"]) == ["count", "name"]


def test_typeddict_with_optional_keys_omits_from_required(ctx: SchemaContext) -> None:
    from typing import TypedDict
    from poethepoet.options.annotations import option_annotation

    @option_annotation
    class _OptionalTD(TypedDict, total=False):
        a: str

    annotation = TypeAnnotation.parse(_OptionalTD)
    schema = translate_type(annotation, ctx)
    assert schema["required"] == []


def test_typeddict_description_from_class_attribute_docstring(ctx: SchemaContext) -> None:
    """
    Verifies that TypedDict descriptions are extracted (not via the
    PoeOptions MRO path, since TypedDicts aren't PoeOptions subclasses).
    """
    from typing import TypedDict
    from poethepoet.options.annotations import option_annotation

    @option_annotation
    class _DescribedTD(TypedDict):
        field: str
        """This description should appear in the schema."""

    annotation = TypeAnnotation.parse(_DescribedTD)
    schema = translate_type(annotation, ctx)
    assert schema["properties"]["field"]["description"] == (
        "This description should appear in the schema."
    )
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `poe test tests/schema/test_translate.py`

Expected: The new tests FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement collection translators**

In `poethepoet/schema/translate.py`, update the imports at the top to include the new types:

```python
from poethepoet.options.annotations import (
    AnyType,
    DictType,
    ListType,
    LiteralType,
    NoneType,
    PrimitiveType,
    TypeAnnotation,
    TypedDictType,
)
```

Add the dispatch branches in `translate_type` before the `NotImplementedError`:

```python
    if isinstance(annotation, ListType):
        return _translate_list(annotation, ctx)
    if isinstance(annotation, DictType):
        return _translate_dict(annotation, ctx)
    if isinstance(annotation, TypedDictType):
        return _translate_typeddict(annotation, ctx)
```

Add the implementations to the bottom of the module:

```python
def _translate_list(annotation: ListType, ctx) -> dict:
    """Translate a ListType / Sequence[X] / tuple[X, ...] annotation."""
    schema: dict[str, Any] = {"type": "array"}

    if not isinstance(annotation._value_type, AnyType):
        schema["items"] = translate_type(annotation._value_type, ctx)

    if (min_length := annotation.metadata_get("min_length")) is not None:
        schema["minItems"] = min_length
    if (max_length := annotation.metadata_get("max_length")) is not None:
        schema["maxItems"] = max_length
    if (examples := annotation.metadata_get("examples")) is not None:
        schema["examples"] = examples

    return schema


def _translate_dict(annotation: DictType, ctx) -> dict:
    """
    Translate a DictType / Mapping[str, V] annotation.

    Note: PoeOptions assumes all dict keys are strings; this matches
    JSON's key-as-string constraint.
    """
    schema: dict[str, Any] = {"type": "object"}

    if not isinstance(annotation._value_type, AnyType):
        schema["additionalProperties"] = translate_type(
            annotation._value_type, ctx
        )

    return schema


def _translate_typeddict(annotation: TypedDictType, ctx) -> dict:
    """
    Translate a TypedDictType. The class is `annotation._annotation`;
    fields and optional-key information are in `annotation._schema` /
    `annotation._optional_keys`.

    Descriptions are routed through ctx.description_for, which dispatches
    to extract_field_descriptions directly for TypedDicts (no MRO walk).
    """
    cls = annotation._annotation
    properties: dict[str, dict] = {}
    required: list[str] = []

    for field_name, field_annotation in annotation._schema.items():
        field_schema = translate_type(field_annotation, ctx)
        if description := ctx.description_for(cls, field_name):
            field_schema["description"] = description
        properties[field_name] = field_schema
        if field_name not in annotation._optional_keys:
            required.append(field_name)

    return {
        "type": "object",
        "properties": properties,
        "required": sorted(required),
        "additionalProperties": False,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poe test tests/schema/test_translate.py`

Expected: All tests PASS (including the new collection tests).

- [ ] **Step 5: Commit**

```bash
git add poethepoet/schema/translate.py tests/schema/test_translate.py
git commit -m "$(cat <<'EOF'
feat: translate list, dict, and TypedDict to JSON Schema

TypedDict descriptions route through SchemaContext.description_for,
which dispatches to extract_field_descriptions directly (TypedDicts
aren't PoeOptions subclasses, so the MRO walk in description_for_field
doesn't apply).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Translate `UnionType` (with `Optional` collapse)

**Files:**

- Modify: `poethepoet/schema/translate.py`
- Modify: `tests/schema/test_translate.py`

**Why:** Unions are the most subtle translator branch. `Optional[X]` (i.e. `X | None`) should collapse — the `None` branch is dropped and the field becomes optional at the parent level (handled by the schema-fragment hook in Task 8, by omitting the field from `required`). Plain unions become `anyOf`.

- [ ] **Step 1: Add failing tests for unions**

Append to `tests/schema/test_translate.py`:

```python
# --- UnionType ---

def test_union_of_str_and_int_to_anyof(ctx: SchemaContext) -> None:
    annotation = TypeAnnotation.parse(str | int)
    schema = translate_type(annotation, ctx)
    assert schema == {
        "anyOf": [
            {"type": "string"},
            {"type": "integer"},
        ]
    }


def test_optional_str_collapses_to_str_schema(ctx: SchemaContext) -> None:
    """
    `Optional[str]` (i.e. `str | None`) translates to just the `str`
    schema; the schema-fragment hook handles "field not required" at the
    object level via the parent's `required` list.
    """
    annotation = TypeAnnotation.parse(str | None)
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "string"}


def test_optional_complex_union_drops_none_branch(ctx: SchemaContext) -> None:
    """A multi-branch union with None should drop the None branch."""
    from typing import Optional
    annotation = TypeAnnotation.parse(Optional[str | int])  # str | int | None
    schema = translate_type(annotation, ctx)
    assert schema == {
        "anyOf": [
            {"type": "string"},
            {"type": "integer"},
        ]
    }


def test_pure_none_union_is_null(ctx: SchemaContext) -> None:
    """Edge case: a union containing only None resolves to null."""
    from typing import Optional
    annotation = TypeAnnotation.parse(Optional[None])
    schema = translate_type(annotation, ctx)
    assert schema == {"type": "null"}
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `poe test tests/schema/test_translate.py::test_union_of_str_and_int_to_anyof tests/schema/test_translate.py::test_optional_str_collapses_to_str_schema tests/schema/test_translate.py::test_optional_complex_union_drops_none_branch tests/schema/test_translate.py::test_pure_none_union_is_null`

Expected: All four FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement the union translator**

In `poethepoet/schema/translate.py`, add `UnionType` to the import list:

```python
from poethepoet.options.annotations import (
    AnyType,
    DictType,
    ListType,
    LiteralType,
    NoneType,
    PrimitiveType,
    TypeAnnotation,
    TypedDictType,
    UnionType,
)
```

Add the dispatch branch in `translate_type` before `NotImplementedError`:

```python
    if isinstance(annotation, UnionType):
        return _translate_union(annotation, ctx)
```

Add the implementation:

```python
def _translate_union(annotation: UnionType, ctx) -> dict:
    """
    Translate a UnionType.

    Drops `NoneType` branches — Optional handling lives at the parent
    object level (a field's optionality is expressed by omitting it from
    the parent's `required` list, not by including null in its schema).

    If only one non-None branch remains, return that branch directly
    (no `anyOf` wrapper). If all branches are None, return a null schema.
    """
    non_none_branches = [
        branch
        for branch in annotation._value_types
        if not isinstance(branch, NoneType)
    ]

    if not non_none_branches:
        return {"type": "null"}

    if len(non_none_branches) == 1:
        return translate_type(non_none_branches[0], ctx)

    return {
        "anyOf": [translate_type(branch, ctx) for branch in non_none_branches]
    }
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `poe test tests/schema/test_translate.py`

Expected: ALL tests PASS (including the four new union tests).

- [ ] **Step 5: Verify the translator handles every TypeAnnotation subclass**

The plan above covers `PrimitiveType`, `LiteralType`, `AnyType`, `NoneType`, `ListType`, `DictType`, `TypedDictType`, `UnionType`. Add a comprehensiveness test to catch any future TypeAnnotation subclass that wasn't accounted for:

Append to `tests/schema/test_translate.py`:

```python
def test_all_type_annotation_subclasses_have_a_translator(ctx: SchemaContext) -> None:
    """
    If a new TypeAnnotation subclass is introduced, this test will fail
    until a translator branch is added.
    """
    from poethepoet.options.annotations import TypeAnnotation

    # Walk the TypeAnnotation subclass tree.
    to_check = [TypeAnnotation]
    leaves: list[type] = []
    while to_check:
        cls = to_check.pop()
        subclasses = cls.__subclasses__()
        if not subclasses:
            leaves.append(cls)
        else:
            to_check.extend(subclasses)

    # For each leaf, construct a representative annotation and translate.
    # The exact construction varies per subclass; this loop simply asserts
    # that NotImplementedError is never raised for known subclasses.
    representative_annotations = {
        "PrimitiveType": TypeAnnotation.parse(str),
        "LiteralType": TypeAnnotation.parse(Literal["a"]),
        "AnyType": TypeAnnotation.parse(Any),
        "NoneType": TypeAnnotation.parse(None),
        "ListType": TypeAnnotation.parse(list),
        "DictType": TypeAnnotation.parse(dict),
        # TypedDictType and UnionType are exercised by dedicated tests.
    }

    for cls in leaves:
        name = cls.__name__
        if name in ("TypedDictType", "UnionType"):
            continue  # exercised by dedicated tests
        annotation = representative_annotations.get(name)
        assert annotation is not None, (
            f"No representative annotation for {name} — add one to keep "
            "this comprehensiveness test honest."
        )
        # Translation should not raise.
        result = translate_type(annotation, ctx)
        assert isinstance(result, dict)
```

- [ ] **Step 6: Run the new comprehensiveness test**

Run: `poe test tests/schema/test_translate.py::test_all_type_annotation_subclasses_have_a_translator`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add poethepoet/schema/translate.py tests/schema/test_translate.py
git commit -m "$(cat <<'EOF'
feat: translate UnionType with Optional collapse

`X | None` collapses to the X schema; the parent object expresses
optionality by omitting the field from its `required` list. Plain
unions become `anyOf`. Adds a comprehensiveness test that catches
any future TypeAnnotation subclass missing a translator branch.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Default `PoeOptions.__schema_fragment__`

**Files:**

- Modify: `poethepoet/options/base.py`
- Create: `tests/schema/test_schema_fragment.py`

**Why:** The default implementation walks all fields on a PoeOptions class, translates each via `translate_type`, attaches descriptions, marks non-optional fields as required, and emits the object schema. Most PoeOptions subclasses inherit this default unchanged.

- [ ] **Step 1: Write failing tests for the default hook**

Create `tests/schema/test_schema_fragment.py`:

```python
"""
Unit tests for PoeOptions.__schema_fragment__ (default) and the
overrides on PoeTask and per-task subclasses.
"""

from __future__ import annotations

from typing import Annotated

import pytest

from poethepoet.options import PoeOptions
from poethepoet.options.annotations import Metadata
from poethepoet.schema.context import SchemaContext


@pytest.fixture
def ctx() -> SchemaContext:
    return SchemaContext(version="0.0.0")


class _Required(PoeOptions):
    name: str
    """The required name."""

    count: int = 0
    """The optional count (has a default)."""


class _Optional(PoeOptions):
    flag: bool | None = None
    """Optional flag."""


def test_default_emits_object_with_properties(ctx: SchemaContext) -> None:
    schema = _Required.__schema_fragment__(ctx)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"name", "count"}


def test_default_marks_required_fields(ctx: SchemaContext) -> None:
    """
    A field without a class-level default and without Optional type
    is required.
    """
    schema = _Required.__schema_fragment__(ctx)
    assert schema["required"] == ["name"]
    # `count` has a default of 0 → not required.


def test_default_attaches_descriptions(ctx: SchemaContext) -> None:
    schema = _Required.__schema_fragment__(ctx)
    assert schema["properties"]["name"]["description"] == "The required name."
    assert schema["properties"]["count"]["description"] == (
        "The optional count (has a default)."
    )


def test_default_excludes_optional_field_from_required(ctx: SchemaContext) -> None:
    schema = _Optional.__schema_fragment__(ctx)
    assert "required" in schema
    assert "flag" not in schema["required"]


def test_default_handles_metadata_constraints(ctx: SchemaContext) -> None:
    class _Constrained(PoeOptions):
        name: Annotated[str, Metadata(pattern=r"^[a-z]+$")] = ""
        """Lowercase name."""

    schema = _Constrained.__schema_fragment__(ctx)
    assert schema["properties"]["name"]["pattern"] == "^[a-z]+$"


def test_default_uses_config_name_for_property_key(ctx: SchemaContext) -> None:
    """
    When a field has Metadata(config_name=...), the schema property key
    must be the config_name, not the Python attribute name.
    """
    class _Renamed(PoeOptions):
        with_: Annotated[str, Metadata(config_name="with")] = ""

    schema = _Renamed.__schema_fragment__(ctx)
    assert "with" in schema["properties"]
    assert "with_" not in schema["properties"]


def test_default_inherits_fields_from_base_class(ctx: SchemaContext) -> None:
    """
    Approach B — full inlining. A subclass's schema_fragment contains
    both its own fields and inherited fields.
    """
    class _Child(_Required):
        extra: str = ""

    schema = _Child.__schema_fragment__(ctx)
    assert set(schema["properties"]) == {"name", "count", "extra"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `poe test tests/schema/test_schema_fragment.py`

Expected: All tests FAIL — `__schema_fragment__` not yet defined on PoeOptions.

- [ ] **Step 3: Implement the default `__schema_fragment__` on `PoeOptions`**

In `poethepoet/options/base.py`, after `description_for_field` (around line 286), add:

```python
    @classmethod
    def __schema_fragment__(cls, ctx: Any) -> dict:
        """
        Emit a JSON Schema fragment describing this options dict.

        Default behavior:
        - Each field becomes a property; the property key is the
          field's config_name if set, else the Python attribute name.
        - Each property's schema is produced by `translate_type` and
          augmented with a description sourced from class-attribute
          docstrings (via `description_for_field`, which walks the MRO).
        - Fields with no class-level default value AND not Optional
          are placed in `required`.
        - `additionalProperties` is `false`.

        Subclasses may override this to handle irregular shapes (e.g.
        switch task case items, recursive task_def references); they
        should call `super().__schema_fragment__(ctx)` to obtain the
        default and then mutate the parts that need customizing.
        """
        from poethepoet.schema.translate import translate_type

        properties: dict[str, dict] = {}
        required: list[str] = []

        for attr_name, type_annotation in cls.get_fields().items():
            # Property name in the schema is the config_name if set.
            schema_key = (
                type_annotation.metadata_get("config_name") or attr_name
            )

            field_schema = translate_type(type_annotation, ctx)
            if description := cls.description_for_field(attr_name):
                field_schema["description"] = description
            properties[schema_key] = field_schema

            # A field is required iff: no class-level default value AND
            # its type isn't Optional. We mirror PoeOptions.parse's logic.
            has_default = hasattr(
                cls, cls.get_field_attribute(attr_name) or attr_name
            )
            if not has_default and not type_annotation.is_optional:
                required.append(schema_key)

        result: dict[str, Any] = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }
        # Always include `required` (possibly empty) for explicit clarity.
        result["required"] = sorted(required)
        return result
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poe test tests/schema/test_schema_fragment.py`

Expected: All tests PASS.

- [ ] **Step 5: Verify no regressions in the rest of the test suite**

Run: `poe test`

Expected: All tests still pass (the new method is additive, not modifying behavior).

- [ ] **Step 6: Commit**

```bash
git add poethepoet/options/base.py tests/schema/test_schema_fragment.py
git commit -m "$(cat <<'EOF'
feat: add default PoeOptions.__schema_fragment__ classmethod

Translates each field via translate_type, attaches docstring-sourced
descriptions, marks non-optional fields without defaults as required,
and sets additionalProperties: false. Property keys honor the
Metadata(config_name=...) renaming convention. Approach B (full
inlining): inherited fields appear in subclass output.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `PoeTask.__schema_fragment__` — wrap TaskOptions with discriminator

**Files:**

- Modify: `poethepoet/task/base.py`
- Modify: `tests/schema/test_schema_fragment.py`

**Why:** `PoeTask` subclasses (`CmdTask`, `ShellTask`, etc.) each represent one branch of the task-def union. Their schema fragment is their `TaskOptions.__schema_fragment__` output augmented with the discriminator key (e.g. `cmd`, `shell`) typed by `__content_type__` (e.g. `str`, `list`), and that key added to `required`.

The default `PoeTask.__schema_fragment__` implementation handles the common case; subclasses with irregular content shapes (Switch, Sequence/Parallel) override.

- [ ] **Step 1: Add failing tests for the PoeTask wrapper**

Append to `tests/schema/test_schema_fragment.py`:

```python
def test_cmd_task_schema_fragment_includes_discriminator(ctx: SchemaContext) -> None:
    from poethepoet.task.cmd import CmdTask

    schema = CmdTask.__schema_fragment__(ctx)
    assert schema["type"] == "object"
    assert "cmd" in schema["properties"]
    assert schema["properties"]["cmd"]["type"] == "string"
    assert "cmd" in schema["required"]
    assert schema["additionalProperties"] is False


def test_cmd_task_schema_fragment_includes_standard_options(ctx: SchemaContext) -> None:
    """
    Approach B — full inlining. CmdTask's schema should include all
    fields inherited from PoeTask.TaskOptions.
    """
    from poethepoet.task.cmd import CmdTask

    schema = CmdTask.__schema_fragment__(ctx)
    # Sampled inherited fields:
    for inherited in ("args", "cwd", "env", "deps", "help"):
        assert inherited in schema["properties"], (
            f"{inherited} should appear inlined on cmd_task"
        )


def test_cmd_task_schema_includes_own_options(ctx: SchemaContext) -> None:
    """CmdTask adds use_exec, empty_glob, ignore_fail."""
    from poethepoet.task.cmd import CmdTask

    schema = CmdTask.__schema_fragment__(ctx)
    assert "use_exec" in schema["properties"]
    assert "empty_glob" in schema["properties"]
    assert "ignore_fail" in schema["properties"]


def test_shell_task_discriminator_is_string() -> None:
    """Validates the discriminator type matches __content_type__."""
    from poethepoet.task.shell import ShellTask

    assert ShellTask.__content_type__ is str


def test_sequence_task_discriminator_is_array(ctx: SchemaContext) -> None:
    """
    For Sequence/Parallel, __content_type__ is list — the discriminator
    appears with `type: array`. Detailed content shape (recursive
    task_def items) is handled by the per-class override in Task 11.
    """
    from poethepoet.task.sequence import SequenceTask

    schema = SequenceTask.__schema_fragment__(ctx)
    # The discriminator key is `sequence` and it must be present and
    # typed as array (the items refinement is the next task).
    assert "sequence" in schema["properties"]
    assert schema["properties"]["sequence"]["type"] == "array"
    assert "sequence" in schema["required"]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `poe test tests/schema/test_schema_fragment.py -k "cmd_task or shell_task or sequence_task"`

Expected: All FAIL — the PoeTask wrapper isn't defined yet, and the default PoeOptions.**schema_fragment** won't include the discriminator.

- [ ] **Step 3: Implement `PoeTask.__schema_fragment__`**

In `poethepoet/task/base.py`, add a classmethod to `PoeTask` (after `get_task_types`, around line 691):

```python
    @classmethod
    def __schema_fragment__(cls, ctx) -> dict:
        """
        Emit the JSON Schema fragment for this task variant.

        Composes `cls.TaskOptions.__schema_fragment__(ctx)` (which gives
        the options-dict shape) with the discriminator key (`cls.__key__`)
        typed by `cls.__content_type__`, and marks the discriminator as
        required.

        Subclasses with irregular content shape override this and call
        `super().__schema_fragment__(ctx)` to get the base assembly,
        then refine specific parts.
        """
        from poethepoet.schema.translate import translate_type
        from poethepoet.options.annotations import TypeAnnotation

        fragment = cls.TaskOptions.__schema_fragment__(ctx)

        # The discriminator key (e.g. "cmd", "shell") with the right
        # content type. We translate __content_type__ as a primitive
        # annotation so str → string, list → array.
        content_annotation = TypeAnnotation.parse(cls.__content_type__)
        content_schema = translate_type(content_annotation, ctx)

        fragment["properties"][cls.__key__] = content_schema
        # Append the discriminator to required (sorted, no duplicates).
        required = set(fragment.get("required", []))
        required.add(cls.__key__)
        fragment["required"] = sorted(required)

        return fragment
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `poe test tests/schema/test_schema_fragment.py`

Expected: All tests PASS.

- [ ] **Step 5: Verify the same wrapper works for executors**

`PoeExecutor.__schema_fragment__` doesn't need a discriminator wrapper because the executor's `ExecutorOptions` already has `type: str` as a field (see `executor/base.py:83`). The default `PoeOptions.__schema_fragment__` on `ExecutorOptions` is enough — but the `type:` field needs to be a `Literal[<key>]` so the schema emits a `const` (or single-element enum). We'll add this in Task 14 via a small override on `PoeExecutor`. For now, leave the executor path alone.

Run a smoke check to confirm:

```bash
python -c "
from poethepoet.schema.context import SchemaContext
from poethepoet.executor.uv import UvExecutor
ctx = SchemaContext(version='0.0.0')
schema = UvExecutor.ExecutorOptions.__schema_fragment__(ctx)
print('Properties:', sorted(schema['properties'].keys()))
print('Required:', schema['required'])
"
```

Expected output: properties include `type`, `extra`, `group`, etc.; `type` is in required. (The exact list depends on UvExecutor.ExecutorOptions's fields.)

- [ ] **Step 6: Commit**

```bash
git add poethepoet/task/base.py tests/schema/test_schema_fragment.py
git commit -m "$(cat <<'EOF'
feat: add PoeTask.__schema_fragment__ wrapping TaskOptions with discriminator

Calls the inherited PoeOptions default for the options shape, then
wraps with the discriminator key (cls.__key__) typed by
cls.__content_type__, and marks it as required. Subclasses with
irregular content shapes (Switch, Sequence, Parallel) will override
and call super() in subsequent tasks.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: `SwitchTask.__schema_fragment__` override

**Files:**

- Modify: `poethepoet/task/switch.py`
- Modify: `tests/schema/test_schema_fragment.py`

**Why:** The `switch` content is `list[dict]` where each item has an optional `case` key alongside an embedded task definition. The default (after Task 11's Sequence/Parallel override) emits `items: {$ref: task_def}`, but switch items have additional structure beyond a plain task — specifically the `case` key. The override emits a dedicated `switch_case_item` definition.

`switch_case_item` shape:

- A `case: str | list[str]` key (optional — its absence means the default branch)
- All the task-def keys (cmd, shell, etc. — i.e. a task_def itself)

In JSON Schema:

```json
"switch_case_item": {
  "allOf": [
    {"$ref": "#/definitions/task_def"},
    {
      "type": "object",
      "properties": {
        "case": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}
      }
    }
  ]
}
```

But that re-introduces the `allOf` + `additionalProperties: false` gotcha — task_def has additionalProperties:false inside its variant branches. So instead, the `switch_case_item` MUST inline rather than refer to task_def. We emit a oneOf over the same variants as task_def, but each variant additionally allows the `case` key.

To keep this manageable, we register a "task_def_with_case" variant in $defs that's identical to task_def but with each variant extended to include the optional `case` key. The orchestrator will build this — see Task 13.

For Task 10 specifically: the `SwitchTask.__schema_fragment__` only refines the `switch` property of its own fragment. The orchestrator handles the items schema via `task_def_with_case`. We just need to make sure that property's value is `{type: array, items: {$ref: "#/definitions/task_def_with_case"}}`.

- [ ] **Step 1: Add a failing test for the switch override**

Append to `tests/schema/test_schema_fragment.py`:

```python
def test_switch_task_items_reference_task_def_with_case(ctx: SchemaContext) -> None:
    """
    SwitchTask's `switch` content is a list of case-items, each of which
    is a task definition extended with an optional `case` key. The schema
    references a dedicated `task_def_with_case` definition.
    """
    from poethepoet.task.switch import SwitchTask

    schema = SwitchTask.__schema_fragment__(ctx)
    items_schema = schema["properties"]["switch"]["items"]
    assert items_schema == {"$ref": "#/definitions/task_def_with_case"}


def test_switch_task_includes_control_property(ctx: SchemaContext) -> None:
    """SwitchTask's TaskOptions has a `control` field that must appear."""
    from poethepoet.task.switch import SwitchTask

    schema = SwitchTask.__schema_fragment__(ctx)
    assert "control" in schema["properties"]
    assert "control" in schema["required"]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `poe test tests/schema/test_schema_fragment.py -k "switch"`

Expected: FAIL — `switch.items` is currently translated from the default annotation, not the `task_def_with_case` reference.

- [ ] **Step 3: Implement the override**

In `poethepoet/task/switch.py`, add a classmethod to `SwitchTask` (after `TaskSpec`, around line 159):

```python
    @classmethod
    def __schema_fragment__(cls, ctx):
        """
        Override: the `switch` content's items are case-aware task defs,
        not plain task defs. Reference `task_def_with_case` (registered
        by the orchestrator in build_schema).
        """
        fragment = super().__schema_fragment__(ctx)
        fragment["properties"]["switch"]["items"] = {
            "$ref": "#/definitions/task_def_with_case"
        }
        return fragment
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poe test tests/schema/test_schema_fragment.py -k "switch"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poethepoet/task/switch.py tests/schema/test_schema_fragment.py
git commit -m "$(cat <<'EOF'
feat: SwitchTask.__schema_fragment__ references task_def_with_case

Switch case items are task definitions with an optional `case` key.
The orchestrator registers the task_def_with_case definition in $defs
(Task 13); this override points switch.items at it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: `SequenceTask` and `ParallelTask` overrides — recursive `task_def` items

**Files:**

- Modify: `poethepoet/task/sequence.py`
- Modify: `poethepoet/task/parallel.py`
- Modify: `tests/schema/test_schema_fragment.py`

**Why:** Sequence/Parallel content items reference the recursive `task_def`. The default would emit the Python annotation's translation (`list[str | dict[str, Any]]` → `items: {anyOf: [{type: string}, {type: object}]}`), which is too permissive and doesn't enforce the discriminated shape.

- [ ] **Step 1: Add failing tests**

Append to `tests/schema/test_schema_fragment.py`:

```python
def test_sequence_items_reference_task_def(ctx: SchemaContext) -> None:
    from poethepoet.task.sequence import SequenceTask

    schema = SequenceTask.__schema_fragment__(ctx)
    assert schema["properties"]["sequence"]["items"] == {
        "$ref": "#/definitions/task_def"
    }


def test_parallel_items_reference_task_def(ctx: SchemaContext) -> None:
    from poethepoet.task.parallel import ParallelTask

    schema = ParallelTask.__schema_fragment__(ctx)
    assert schema["properties"]["parallel"]["items"] == {
        "$ref": "#/definitions/task_def"
    }
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `poe test tests/schema/test_schema_fragment.py -k "sequence_items or parallel_items"`

Expected: FAIL.

- [ ] **Step 3: Add the override on `SequenceTask`**

In `poethepoet/task/sequence.py`, add a classmethod to `SequenceTask` (after the `TaskSpec` class, around line 120):

```python
    @classmethod
    def __schema_fragment__(cls, ctx):
        """
        Override: sequence items reference the recursive task_def union
        (registered by the orchestrator).
        """
        fragment = super().__schema_fragment__(ctx)
        fragment["properties"]["sequence"]["items"] = {
            "$ref": "#/definitions/task_def"
        }
        return fragment
```

- [ ] **Step 4: Add the override on `ParallelTask`**

In `poethepoet/task/parallel.py`, add an analogous classmethod to `ParallelTask`:

```python
    @classmethod
    def __schema_fragment__(cls, ctx):
        """
        Override: parallel items reference the recursive task_def union.
        """
        fragment = super().__schema_fragment__(ctx)
        fragment["properties"]["parallel"]["items"] = {
            "$ref": "#/definitions/task_def"
        }
        return fragment
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `poe test tests/schema/test_schema_fragment.py -k "sequence_items or parallel_items"`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add poethepoet/task/sequence.py poethepoet/task/parallel.py tests/schema/test_schema_fragment.py
git commit -m "$(cat <<'EOF'
feat: Sequence/Parallel __schema_fragment__ overrides for recursive task_def

Both task types' content items reference the recursive task_def
definition registered by the orchestrator (Task 13). The default
translator would emit a too-permissive {string | object} union.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: `ArgSpec.__schema_fragment__` override

**Files:**

- Modify: `poethepoet/task/args.py`
- Modify: `tests/schema/test_schema_fragment.py`

**Why:** `ArgSpec` is a `PoeOptions` subclass, so the default `__schema_fragment__` mostly works for the per-arg dict shape. The wrinkle: the `options` field is computed by the normalizer (it's set from the `name` field if not provided), so for the SCHEMA we shouldn't mark `options` as required — users don't provide it directly in most cases. Confirm by reading args.py: `options: Sequence[str]` has no default, but the normalizer always fills it in. From a schema perspective, accepting input where `options` is absent is correct.

The outer list-vs-dict polymorphism of the `args` _field_ (a task-level option) is handled by the orchestrator in Task 13 — NOT by ArgSpec itself.

- [ ] **Step 1: Add a failing test for ArgSpec's fragment**

Append to `tests/schema/test_schema_fragment.py`:

```python
def test_argspec_schema_fragment_has_expected_properties(ctx: SchemaContext) -> None:
    from poethepoet.task.args import ArgSpec

    schema = ArgSpec.__schema_fragment__(ctx)
    expected = {
        "default", "help", "name", "options", "positional",
        "required", "type", "multiple", "choices",
    }
    assert set(schema["properties"]) >= expected


def test_argspec_options_field_not_in_required(ctx: SchemaContext) -> None:
    """
    `options` is normalizer-supplied; users typically don't write it
    directly. Mark it optional in the schema.
    """
    from poethepoet.task.args import ArgSpec

    schema = ArgSpec.__schema_fragment__(ctx)
    assert "options" not in schema["required"]


def test_argspec_type_field_is_enum_of_string_float_integer_boolean(ctx: SchemaContext) -> None:
    """
    `type` is Literal["string", "float", "integer", "boolean"], so the
    schema property should be `{type: string, enum: [...]}`.
    """
    from poethepoet.task.args import ArgSpec

    schema = ArgSpec.__schema_fragment__(ctx)
    type_schema = schema["properties"]["type"]
    assert type_schema["type"] == "string"
    assert set(type_schema["enum"]) == {"string", "float", "integer", "boolean"}
```

- [ ] **Step 2: Run the new tests to verify what fails**

Run: `poe test tests/schema/test_schema_fragment.py -k "argspec"`

Expected: `test_argspec_options_field_not_in_required` FAILS (others may pass already because the default fragment naturally produces what they assert).

- [ ] **Step 3: Add the override on `ArgSpec`**

In `poethepoet/task/args.py`, add a classmethod to `ArgSpec` (around line 142, after `validate`):

```python
    @classmethod
    def __schema_fragment__(cls, ctx):
        """
        Override: `options` is normalizer-supplied (derived from `name`
        if not provided), so it shouldn't be required in the schema.
        """
        fragment = super().__schema_fragment__(ctx)
        fragment["required"] = sorted(
            key for key in fragment.get("required", []) if key != "options"
        )
        return fragment
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poe test tests/schema/test_schema_fragment.py -k "argspec"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poethepoet/task/args.py tests/schema/test_schema_fragment.py
git commit -m "$(cat <<'EOF'
feat: ArgSpec.__schema_fragment__ removes `options` from required

The `options` field is normalizer-supplied (computed from `name` when
not provided), so the schema accepts arg-spec input without it. The
outer list-vs-dict polymorphism of the `args` field is handled by the
orchestrator (Task 13), not on ArgSpec itself.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: `task_def` union with forward-compat fallback

**Files:**

- Modify: `poethepoet/task/base.py` (add `PoeTask.get_task_class` public accessor)
- Modify: `poethepoet/schema/fragments.py`
- Create: `tests/schema/test_fragments.py`

**Why:** This is one of the two main cross-cutting compositions the orchestrator handles. The `task_def` union captures every shape that "a task" can take:

1. A bare string (`"echo hello"` → uses `default_task_type`, defaulting to `cmd`)
2. A bare array (`["task1", "task2"]` → uses `default_array_task_type`, defaulting to `sequence`)
3. A dict with exactly one recognized task-type key as discriminator (`{cmd = "...", env = {...}}`)
4. A dict with NO recognized task-type key — the forward-compat fallback

We also need a `task_def_with_case` variant for switch case items (Task 10 references it).

This task also adds `PoeTask.get_task_class(key)` as a public accessor — `PoeTask.__task_types` is private (name-mangled to `_PoeTask__task_types`), and the schema generator shouldn't reach across visibility boundaries to read it. The accessor is the public read-side complement to the existing `MetaPoeTask.__init__` registration.

- [ ] **Step 1: Add `PoeTask.get_task_class` classmethod**

In `poethepoet/task/base.py`, locate the existing classmethods on `PoeTask` (around line 670–690, near `get_task_types`). Add:

```python
    @classmethod
    def get_task_class(cls, key: str) -> type[PoeTask]:
        """
        Look up a registered PoeTask subclass by its `__key__`.

        Public read-side complement to MetaPoeTask's registration logic.
        Raises KeyError if the key isn't registered.
        """
        if key not in cls.__task_types:
            raise KeyError(f"Unknown task type {key!r}")
        return cls.__task_types[key]
```

(`cls.__task_types` works inside `PoeTask`'s class body because the name mangling resolves to `_PoeTask__task_types` exactly where it's declared.)

Add a unit test in `tests/options/test_options.py`:

```python
def test_poe_task_get_task_class_returns_registered_class() -> None:
    from poethepoet.task.base import PoeTask
    from poethepoet.task.cmd import CmdTask

    assert PoeTask.get_task_class("cmd") is CmdTask


def test_poe_task_get_task_class_raises_for_unknown_key() -> None:
    import pytest
    from poethepoet.task.base import PoeTask

    with pytest.raises(KeyError, match="Unknown task type"):
        PoeTask.get_task_class("not_a_real_task_type")
```

Run: `poe test tests/options/test_options.py -k "get_task_class"`

Expected: PASS (after the classmethod is added).

- [ ] **Step 2: Write failing tests for `task_def_schema` and `task_def_with_case_schema`**

Create `tests/schema/test_fragments.py`:

```python
"""
Unit tests for cross-cutting schema fragments — task_def union,
executor tagged union, env/envfile polymorphism, tasks/groups maps.
"""

from __future__ import annotations

import pytest

from poethepoet.schema.context import SchemaContext
from poethepoet.schema.fragments import (
    task_def_schema,
    task_def_with_case_schema,
)


@pytest.fixture
def ctx() -> SchemaContext:
    return SchemaContext(version="0.0.0")


def test_task_def_includes_string_branch(ctx: SchemaContext) -> None:
    """Bare string is one of the accepted shapes."""
    schema = task_def_schema(ctx)
    string_branches = [
        branch for branch in schema["oneOf"]
        if branch.get("type") == "string"
    ]
    assert len(string_branches) == 1


def test_task_def_includes_array_branch(ctx: SchemaContext) -> None:
    """Bare array is one of the accepted shapes."""
    schema = task_def_schema(ctx)
    array_branches = [
        branch for branch in schema["oneOf"]
        if branch.get("type") == "array"
    ]
    assert len(array_branches) == 1
    # Items recurse into task_def.
    assert array_branches[0]["items"] == {"$ref": "#/definitions/task_def"}


def test_task_def_includes_branch_per_registered_task_type(ctx: SchemaContext) -> None:
    """
    Each task type registered via MetaPoeTask appears as a $ref branch.
    """
    from poethepoet.task.base import PoeTask

    schema = task_def_schema(ctx)
    refs = {
        branch["$ref"] for branch in schema["oneOf"]
        if "$ref" in branch
    }
    expected_refs = {
        f"#/definitions/{key}_task"
        for key in PoeTask.get_task_types()
    }
    assert expected_refs.issubset(refs)


def test_task_def_includes_forward_compat_fallback(ctx: SchemaContext) -> None:
    """
    The fallback branch accepts any object that doesn't contain a known
    discriminator key — forward compatibility with future task types.
    """
    from poethepoet.task.base import PoeTask

    schema = task_def_schema(ctx)
    fallbacks = [
        branch for branch in schema["oneOf"]
        if branch.get("type") == "object" and "not" in branch
    ]
    assert len(fallbacks) == 1
    not_clause = fallbacks[0]["not"]
    assert "anyOf" in not_clause
    forbidden_keys = {
        clause["required"][0]
        for clause in not_clause["anyOf"]
    }
    assert forbidden_keys == set(PoeTask.get_task_types())


def test_task_def_registers_per_task_definitions_in_ctx(ctx: SchemaContext) -> None:
    """
    After calling task_def_schema(ctx), the context's definitions should
    contain entries for every task variant (cmd_task, shell_task, etc.).
    """
    task_def_schema(ctx)
    from poethepoet.task.base import PoeTask
    for key in PoeTask.get_task_types():
        assert f"{key}_task" in ctx.definitions


def test_task_def_with_case_schema_has_case_key_in_each_variant(ctx: SchemaContext) -> None:
    """
    Every task variant inside task_def_with_case gains an optional
    `case` key (used by switch).
    """
    schema = task_def_with_case_schema(ctx)
    # The forward-compat fallback may not have an explicit `case` key
    # (its `additionalProperties: true` covers it). Focus on the
    # explicit variants.
    for branch in schema["oneOf"]:
        if "$ref" not in branch and branch.get("type") == "object" and "properties" in branch:
            assert "case" in branch["properties"], (
                f"Variant {branch!r} should have a `case` property"
            )
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `poe test tests/schema/test_fragments.py`

Expected: All FAIL — `task_def_schema` and `task_def_with_case_schema` not yet defined.

- [ ] **Step 4: Implement `task_def_schema` and `task_def_with_case_schema`**

In `poethepoet/schema/fragments.py`, replace the module body with:

```python
"""
Cross-cutting JSON Schema fragments that aren't owned by any single
PoeOptions class — the task_def union (incl. forward-compat fallback),
the executor tagged union, env/envfile value polymorphism, and the
patternProperties for the tasks/groups maps.
"""

from __future__ import annotations

from typing import Any

from poethepoet.schema.context import SchemaContext


def task_def_schema(ctx: SchemaContext) -> dict:
    """
    Build the task_def union — every accepted shape for "a task" in
    poe config: bare string (default_task_type), bare array
    (default_array_task_type), dict with a recognized discriminator key,
    or dict with no recognized key (forward-compat fallback).

    Side effect: each task variant's schema is registered in ctx.definitions.
    """
    from poethepoet.task.base import PoeTask

    # Register each task variant under "<key>_task" in $defs.
    task_keys = sorted(PoeTask.get_task_types())
    for key in task_keys:
        task_cls = PoeTask.get_task_class(key)
        ctx.register(f"{key}_task", task_cls.__schema_fragment__(ctx))

    branches: list[dict] = [
        {"type": "string"},
        {
            "type": "array",
            "items": {"$ref": "#/definitions/task_def"},
        },
    ]

    for key in task_keys:
        branches.append({"$ref": f"#/definitions/{key}_task"})

    # Forward-compat fallback: a dict that has none of the known
    # discriminator keys.
    branches.append({
        "type": "object",
        "additionalProperties": True,
        "not": {
            "anyOf": [
                {"required": [key]} for key in task_keys
            ],
        },
    })

    return {"oneOf": branches}


def task_def_with_case_schema(ctx: SchemaContext) -> dict:
    """
    Like task_def, but every explicit task-variant branch additionally
    accepts an optional `case` key. Used inside switch tasks.

    The case key accepts either a single string or a list of strings.
    """
    from poethepoet.task.base import PoeTask

    case_value_schema = {
        "anyOf": [
            {"type": "string"},
            {"type": "array", "items": {"type": "string"}},
        ]
    }

    # Build with-case variants. Each variant inlines the same options as
    # the corresponding _task definition but with an added `case`
    # property. We pull the registered definition from ctx (task_def_schema
    # must have been called first; the orchestrator guarantees ordering).
    task_keys = sorted(PoeTask.get_task_types())
    branches: list[dict] = []

    for key in task_keys:
        # Pull the variant's full schema from ctx.definitions and copy it
        # before mutating.
        variant = dict(ctx.definitions[f"{key}_task"])
        # Properties is a dict; copy and add `case`.
        variant["properties"] = dict(variant["properties"])
        variant["properties"]["case"] = case_value_schema
        # Register under a distinct name so editor tooling can jump
        # to either form.
        ctx.register(f"{key}_task_with_case", variant)
        branches.append({"$ref": f"#/definitions/{key}_task_with_case"})

    # Forward-compat fallback — same shape as in task_def_schema, but
    # additionalProperties: true means any case-like key is also fine.
    branches.append({
        "type": "object",
        "additionalProperties": True,
        "not": {
            "anyOf": [
                {"required": [key]} for key in task_keys
            ],
        },
    })

    return {"oneOf": branches}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `poe test tests/schema/test_fragments.py`

Expected: All tests PASS.

- [ ] **Step 6: Register task_def itself in ctx (so the recursive $ref resolves)**

Edit `task_def_schema` so that, after building the union, it registers itself in ctx:

```python
    result = {"oneOf": branches}
    ctx.register("task_def", result)
    return result
```

Add a test to confirm:

Append to `tests/schema/test_fragments.py`:

```python
def test_task_def_schema_registers_itself(ctx: SchemaContext) -> None:
    schema = task_def_schema(ctx)
    assert ctx.definitions["task_def"] == schema
```

- [ ] **Step 7: Run the test to verify**

Run: `poe test tests/schema/test_fragments.py::test_task_def_schema_registers_itself`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add poethepoet/task/base.py poethepoet/schema/fragments.py tests/options/test_options.py tests/schema/test_fragments.py
git commit -m "$(cat <<'EOF'
feat: task_def union with forward-compat fallback

Composes every task variant (registered via MetaPoeTask) into a
oneOf, plus the bare-string and bare-array shorthand branches, plus
a forward-compat fallback branch that accepts any dict without a
recognized discriminator. Also emits task_def_with_case for switch
case items.

Adds PoeTask.get_task_class(key) as a public read-side accessor to
the task type registry, replacing what would otherwise require
reaching into name-mangled private state from the schema generator.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Executor tagged union

**Files:**

- Modify: `poethepoet/executor/base.py` (add `PoeExecutor.get_executor_class` public accessor)
- Modify: `poethepoet/schema/fragments.py`
- Modify: `tests/schema/test_fragments.py`

**Why:** Executors are discriminated by a `type:` field (a proper tag). Each registered executor's `ExecutorOptions` becomes a branch. Per-variant, `type` should appear as `{const: <key>}` (or single-element `enum`).

Currently `PoeExecutor.ExecutorOptions.type` is just `str`. Adding `type: Literal["poetry"]` etc. on each subclass would be the most declarative approach (mirroring the Phase 1 Literal-tightening pattern), but only `UvExecutor` and `VirtualenvExecutor` currently have their own `ExecutorOptions` subclass — `PoetryExecutor`, `SimpleExecutor`, and the implicit `auto` all inherit the bare `type: str`. Adding empty `ExecutorOptions` subclasses to those purely for the Literal narrowing creates more churn than the alternative. The orchestrator-level approach (rewrite the `type` property schema to `{const: <key>}` after calling `__schema_fragment__`) is contained to `fragments.py` and adds no new ExecutorOptions classes.

This task also adds `PoeExecutor.get_executor_class(key)` as the public read-side complement to the registry, matching the `PoeTask.get_task_class` addition from Task 13.

- [ ] **Step 1: Add `PoeExecutor.get_executor_class` classmethod**

In `poethepoet/executor/base.py`, locate the existing classmethods on `PoeExecutor` (search for `validate_config` or `works_with_context`). Add:

```python
    @classmethod
    def get_executor_class(cls, key: str) -> type[PoeExecutor]:
        """
        Look up a registered PoeExecutor subclass by its `__key__`.

        Public read-side complement to MetaPoeExecutor's registration logic.
        Raises KeyError if the key isn't registered.

        Note: "auto" is NOT registered as a PoeExecutor subclass — it's a
        meta-option that PoeExecutor.validate_config resolves to one of the
        concrete subclasses at runtime. Callers that need to enumerate
        "every accepted executor type" must add "auto" explicitly.
        """
        if key not in cls.__executor_types:
            raise KeyError(f"Unknown executor type {key!r}")
        return cls.__executor_types[key]


    @classmethod
    def get_executor_types(cls) -> tuple[str, ...]:
        """
        Return all registered executor keys (in registration order).
        Mirrors PoeTask.get_task_types().
        """
        return tuple(cls.__executor_types.keys())
```

Add unit tests in `tests/options/test_options.py`:

```python
def test_poe_executor_get_executor_class_returns_registered_class() -> None:
    from poethepoet.executor.base import PoeExecutor
    from poethepoet.executor.poetry import PoetryExecutor

    assert PoeExecutor.get_executor_class("poetry") is PoetryExecutor


def test_poe_executor_get_executor_class_raises_for_unknown_key() -> None:
    import pytest
    from poethepoet.executor.base import PoeExecutor

    with pytest.raises(KeyError, match="Unknown executor type"):
        PoeExecutor.get_executor_class("not_a_real_executor")


def test_poe_executor_get_executor_types_includes_known_keys() -> None:
    from poethepoet.executor.base import PoeExecutor

    keys = set(PoeExecutor.get_executor_types())
    # "auto" is intentionally NOT in the registry.
    for expected in ("poetry", "uv", "virtualenv", "simple"):
        assert expected in keys
    assert "auto" not in keys
```

Run: `poe test tests/options/test_options.py -k "get_executor_class or get_executor_types"`

Expected: PASS (after the classmethods are added).

- [ ] **Step 2: Write a failing test for the tagged union**

Append to `tests/schema/test_fragments.py`:

```python
def test_executor_option_includes_shorthand_string(ctx: SchemaContext) -> None:
    """A bare string like "poetry" or "auto" should be accepted."""
    from poethepoet.schema.fragments import executor_option_schema

    schema = executor_option_schema(ctx)
    string_branches = [
        b for b in schema["oneOf"]
        if b.get("type") == "string" and "enum" in b
    ]
    assert len(string_branches) == 1
    # Contains each registered executor key plus "auto".
    enum_values = set(string_branches[0]["enum"])
    assert "auto" in enum_values
    assert "poetry" in enum_values
    assert "uv" in enum_values


def test_executor_option_includes_per_executor_dict_branches(ctx: SchemaContext) -> None:
    from poethepoet.schema.fragments import executor_option_schema

    schema = executor_option_schema(ctx)
    ref_branches = {
        b["$ref"] for b in schema["oneOf"] if "$ref" in b
    }
    # Each registered executor has its own definition.
    assert "#/definitions/executor_poetry" in ref_branches
    assert "#/definitions/executor_uv" in ref_branches


def test_executor_uv_type_is_const_uv(ctx: SchemaContext) -> None:
    """The `type` field on uv's executor branch is constrained."""
    from poethepoet.schema.fragments import executor_option_schema

    executor_option_schema(ctx)  # populates ctx.definitions
    uv_schema = ctx.definitions["executor_uv"]
    assert uv_schema["properties"]["type"] in (
        {"type": "string", "enum": ["uv"]},
        {"const": "uv"},
    )
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `poe test tests/schema/test_fragments.py -k "executor"`

Expected: FAIL — `executor_option_schema` not defined.

- [ ] **Step 4: Implement `executor_option_schema`**

Add to `poethepoet/schema/fragments.py`:

```python
def executor_option_schema(ctx: SchemaContext) -> dict:
    """
    Build the executor option's discriminated union — over the `type:`
    field. Each registered executor becomes a `#/definitions/executor_<key>`.
    A shorthand string form accepts the bare type name (`"poetry"`,
    `"auto"`, etc.).

    "auto" is a known exception: it's the user-facing default but is
    handled specially by PoeExecutor.validate_config rather than being
    registered as a PoeExecutor subclass. We synthesize a minimal
    executor_auto definition for it.

    Side effect: registers each per-executor definition in ctx.definitions
    and registers the executor_option definition itself.
    """
    from poethepoet.executor.base import PoeExecutor

    executor_keys = sorted(PoeExecutor.get_executor_types())
    # Include "auto" in the shorthand-string enum even though it isn't
    # in the registry.
    enum_keys = sorted(set(executor_keys) | {"auto"})

    branches: list[dict] = [
        {"type": "string", "enum": enum_keys},
    ]

    for key in executor_keys:
        executor_cls = PoeExecutor.get_executor_class(key)
        executor_schema = executor_cls.ExecutorOptions.__schema_fragment__(ctx)
        # Tighten the `type` property to a single-value enum (const
        # equivalent in draft-07).
        executor_schema["properties"] = dict(executor_schema["properties"])
        executor_schema["properties"]["type"] = {
            "type": "string",
            "enum": [key],
        }
        ctx.register(f"executor_{key}", executor_schema)
        branches.append({"$ref": f"#/definitions/executor_{key}"})

    # Synthesize a minimal executor_auto definition since "auto" isn't a
    # registered class.
    ctx.register("executor_auto", {
        "type": "object",
        "additionalProperties": False,
        "required": ["type"],
        "properties": {"type": {"type": "string", "enum": ["auto"]}},
    })
    branches.append({"$ref": "#/definitions/executor_auto"})

    result = {"oneOf": branches}
    ctx.register("executor_option", result)
    return result
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `poe test tests/schema/test_fragments.py -k "executor"`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add poethepoet/executor/base.py poethepoet/schema/fragments.py tests/options/test_options.py tests/schema/test_fragments.py
git commit -m "$(cat <<'EOF'
feat: executor tagged union with per-executor definitions

Builds a oneOf over the registered PoeExecutor subclasses. Each
variant is the executor's ExecutorOptions.__schema_fragment__ with
the `type` property tightened to a single-value enum (matching the
executor's __key__). Includes a shorthand string-enum branch and a
synthetic executor_auto definition (since "auto" is handled by
validate_config rather than registered as a subclass).

Adds PoeExecutor.get_executor_class(key) and get_executor_types() as
public read-side accessors to the executor registry, mirroring the
PoeTask additions from the previous commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: `env_option`, `envfile_option`, and `args_option` polymorphism

**Files:**

- Modify: `poethepoet/schema/fragments.py`
- Modify: `tests/schema/test_fragments.py`

**Why:** Three places where the runtime accepts multiple shapes that the schema must enumerate:

1. **env** — `Mapping[str, str | EnvDefault]`. The schema is `{type: object, additionalProperties: <env_value_schema>}` where the value schema is `{anyOf: [{type: string}, {$ref: env_default}]}`.
2. **envfile** — `str | Sequence[str] | EnvfileOption`. A flat anyOf: bare string, array of strings, or the `EnvfileOption` TypedDict.
3. **args** — `dict | list | None`. The outer polymorphism: a list of (string|ArgSpec-dict) items OR a dict mapping arg-name to ArgSpec-dict (with the inner `name` omitted, since it's the key).

- [ ] **Step 1: Write failing tests for env / envfile / args**

Append to `tests/schema/test_fragments.py`:

```python
def test_env_option_schema_accepts_string_and_env_default_values(ctx: SchemaContext) -> None:
    from poethepoet.schema.fragments import env_option_schema

    schema = env_option_schema(ctx)
    assert schema["type"] == "object"
    # additionalProperties is a union: string OR env_default $ref
    ap = schema["additionalProperties"]
    assert "anyOf" in ap
    branches = ap["anyOf"]
    assert {"type": "string"} in branches
    assert any("$ref" in b and b["$ref"].endswith("env_default") for b in branches)


def test_env_default_registered(ctx: SchemaContext) -> None:
    from poethepoet.schema.fragments import env_option_schema
    env_option_schema(ctx)
    assert "env_default" in ctx.definitions
    env_default = ctx.definitions["env_default"]
    assert env_default["properties"]["default"] == {"type": "string"}
    assert env_default["required"] == ["default"]


def test_envfile_option_schema_includes_three_shapes(ctx: SchemaContext) -> None:
    from poethepoet.schema.fragments import envfile_option_schema

    schema = envfile_option_schema(ctx)
    assert "anyOf" in schema
    branches = schema["anyOf"]
    # Bare string, array of strings, envfile_full TypedDict
    assert {"type": "string"} in branches
    assert any(
        b.get("type") == "array" and b.get("items") == {"type": "string"}
        for b in branches
    )
    assert any("$ref" in b for b in branches)


def test_args_option_schema_accepts_list_or_dict(ctx: SchemaContext) -> None:
    from poethepoet.schema.fragments import args_option_schema

    schema = args_option_schema(ctx)
    assert "anyOf" in schema
    branches = schema["anyOf"]
    # List form: array of (string | args_item)
    list_branches = [b for b in branches if b.get("type") == "array"]
    assert list_branches
    # Dict form: object mapping arg-name to args_item
    dict_branches = [b for b in branches if b.get("type") == "object"]
    assert dict_branches


def test_args_item_registered(ctx: SchemaContext) -> None:
    """The per-arg ArgSpec shape is in definitions."""
    from poethepoet.schema.fragments import args_option_schema
    args_option_schema(ctx)
    assert "args_item" in ctx.definitions
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `poe test tests/schema/test_fragments.py -k "env or args"`

Expected: FAIL — the schemas don't exist yet.

- [ ] **Step 3: Implement env_option_schema and envfile_option_schema**

Add to `poethepoet/schema/fragments.py`:

```python
def env_option_schema(ctx: SchemaContext) -> dict:
    """
    Build the env option's schema: `{type: object, additionalProperties:
    <string | env_default>}`. Keys are unconstrained env var names.

    Registers env_default in ctx.definitions.
    """
    from poethepoet.config.primitives import EnvDefault
    from poethepoet.options.annotations import TypeAnnotation
    from poethepoet.schema.translate import translate_type

    # Translate EnvDefault as a TypedDict.
    env_default_annotation = TypeAnnotation.parse(EnvDefault)
    env_default_schema = translate_type(env_default_annotation, ctx)
    ctx.register("env_default", env_default_schema)

    value_schema = {
        "anyOf": [
            {"type": "string"},
            {"$ref": "#/definitions/env_default"},
        ]
    }

    result = {
        "type": "object",
        "additionalProperties": value_schema,
    }
    ctx.register("env_option", result)
    return result


def envfile_option_schema(ctx: SchemaContext) -> dict:
    """
    Build the envfile option's schema. Three accepted shapes:
    - Bare string (one envfile path)
    - Array of strings (multiple paths)
    - EnvfileOption TypedDict with expected/optional keys

    Registers envfile_full (the TypedDict shape) in ctx.definitions.
    """
    from poethepoet.config.primitives import EnvfileOption
    from poethepoet.options.annotations import TypeAnnotation
    from poethepoet.schema.translate import translate_type

    envfile_full_annotation = TypeAnnotation.parse(EnvfileOption)
    envfile_full_schema = translate_type(envfile_full_annotation, ctx)
    ctx.register("envfile_full", envfile_full_schema)

    result = {
        "anyOf": [
            {"type": "string"},
            {"type": "array", "items": {"type": "string"}},
            {"$ref": "#/definitions/envfile_full"},
        ]
    }
    ctx.register("envfile_option", result)
    return result


def args_option_schema(ctx: SchemaContext) -> dict:
    """
    Build the args option's schema. Two accepted top-level shapes:
    - List of (string | args_item) — each item declares one argument.
    - Dict mapping arg-name to args_item (with `name` omitted from
      the inner — it's the dict key).

    Registers args_item (the ArgSpec shape) in ctx.definitions.
    """
    from poethepoet.task.args import ArgSpec

    args_item_schema = ArgSpec.__schema_fragment__(ctx)
    ctx.register("args_item", args_item_schema)

    # For the dict form, the `name` key must NOT appear inside each value
    # (it's the dict key). Build a separate args_item_no_name variant.
    args_item_no_name = dict(args_item_schema)
    args_item_no_name["properties"] = {
        k: v for k, v in args_item_schema["properties"].items() if k != "name"
    }
    args_item_no_name["required"] = sorted(
        k for k in args_item_schema.get("required", []) if k != "name"
    )
    ctx.register("args_item_no_name", args_item_no_name)

    result = {
        "anyOf": [
            {
                "type": "array",
                "items": {
                    "anyOf": [
                        {"type": "string"},
                        {"$ref": "#/definitions/args_item"},
                    ],
                },
            },
            {
                "type": "object",
                "additionalProperties": {
                    "$ref": "#/definitions/args_item_no_name"
                },
            },
        ]
    }
    ctx.register("args_option", result)
    return result
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poe test tests/schema/test_fragments.py -k "env or envfile or args"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poethepoet/schema/fragments.py tests/schema/test_fragments.py
git commit -m "$(cat <<'EOF'
feat: env_option, envfile_option, args_option polymorphism

Three places where the runtime accepts multiple shapes:
- env: mapping with string | env_default values
- envfile: string | array of strings | envfile_full TypedDict
- args: list of (string | args_item) OR dict to args_item_no_name

Each registers the inner shape(s) in ctx.definitions; outer union
returns the polymorphic schema for orchestrator use.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: `tasks_map_schema` and `groups_map_schema` with patternProperties

**Files:**

- Modify: `poethepoet/schema/fragments.py`
- Modify: `tests/schema/test_fragments.py`

**Why:** The `tasks` map's keys must match `_TASK_NAME_PATTERN` (in task/base.py) PLUS start with letter/underscore. The `groups` map's keys match `_GROUP_NAME_PATTERN` (Task 1 lifted to module scope in partition.py).

For tasks: the runtime check is "first char is letter or underscore" AND "remaining chars are alphanumeric, colon, underscore, dash, plus". The combined regex: `^[A-Za-z_][\w\-:+]*$`. (The existing `_TASK_NAME_PATTERN` is `r"^\w[\w\d\-\_\+\:]*$"` which allows digit-first names — but the runtime explicitly rejects those in `_base_validations`. The schema should enforce the tighter rule.)

- [ ] **Step 1: Write failing tests**

Append to `tests/schema/test_fragments.py`:

```python
def test_tasks_map_schema_has_pattern_properties(ctx: SchemaContext) -> None:
    from poethepoet.schema.fragments import tasks_map_schema

    schema = tasks_map_schema(ctx)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "patternProperties" in schema
    # Exactly one pattern entry — the task-name regex.
    assert len(schema["patternProperties"]) == 1
    pattern, value_schema = next(iter(schema["patternProperties"].items()))
    # Pattern starts with letter or underscore.
    import re
    compiled = re.compile(pattern)
    assert compiled.fullmatch("my_task")
    assert compiled.fullmatch("Task-1")
    assert not compiled.fullmatch("1bad")  # digit-first rejected
    assert not compiled.fullmatch("bad name")  # space rejected


def test_tasks_map_values_reference_task_def(ctx: SchemaContext) -> None:
    from poethepoet.schema.fragments import (
        tasks_map_schema, task_def_schema,
    )
    task_def_schema(ctx)  # populate task_def first
    schema = tasks_map_schema(ctx)
    value_schema = next(iter(schema["patternProperties"].values()))
    assert value_schema == {"$ref": "#/definitions/task_def"}


def test_groups_map_schema_imports_group_name_pattern(ctx: SchemaContext) -> None:
    from poethepoet.schema.fragments import groups_map_schema
    from poethepoet.config.partition import _GROUP_NAME_PATTERN

    schema = groups_map_schema(ctx)
    pattern = next(iter(schema["patternProperties"].keys()))
    # The pattern from the constant should be the same regex.
    assert pattern == _GROUP_NAME_PATTERN.pattern


def test_groups_map_values_reference_task_group(ctx: SchemaContext) -> None:
    from poethepoet.schema.fragments import groups_map_schema
    schema = groups_map_schema(ctx)
    value_schema = next(iter(schema["patternProperties"].values()))
    assert value_schema == {"$ref": "#/definitions/task_group"}
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `poe test tests/schema/test_fragments.py -k "tasks_map or groups_map"`

Expected: FAIL.

- [ ] **Step 3: Implement `tasks_map_schema` and `groups_map_schema`**

Add to `poethepoet/schema/fragments.py`:

```python
# Pattern matching the runtime task-name rule: first character must be a
# letter or underscore (the `_base_validations` check), followed by any
# combination of word chars, colon, underscore, dash, plus.
_TASKS_MAP_KEY_PATTERN = r"^[A-Za-z_][\w\-:+]*$"


def tasks_map_schema(ctx: SchemaContext) -> dict:
    """
    Build the schema for the `tasks` map: keys match the task-name
    pattern, values are task definitions.
    """
    result = {
        "type": "object",
        "additionalProperties": False,
        "patternProperties": {
            _TASKS_MAP_KEY_PATTERN: {"$ref": "#/definitions/task_def"},
        },
    }
    ctx.register("tasks_map", result)
    return result


def groups_map_schema(ctx: SchemaContext) -> dict:
    """
    Build the schema for the `groups` map: keys match the group-name
    pattern (imported from config/partition.py — single source of truth),
    values reference the task_group TypedDict.
    """
    from poethepoet.config.partition import _GROUP_NAME_PATTERN, TaskGroup
    from poethepoet.options.annotations import TypeAnnotation
    from poethepoet.schema.translate import translate_type

    task_group_annotation = TypeAnnotation.parse(TaskGroup)
    task_group_schema = translate_type(task_group_annotation, ctx)
    ctx.register("task_group", task_group_schema)

    result = {
        "type": "object",
        "additionalProperties": False,
        "patternProperties": {
            _GROUP_NAME_PATTERN.pattern: {"$ref": "#/definitions/task_group"},
        },
    }
    ctx.register("groups_map", result)
    return result
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poe test tests/schema/test_fragments.py -k "tasks_map or groups_map"`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poethepoet/schema/fragments.py tests/schema/test_fragments.py
git commit -m "$(cat <<'EOF'
feat: tasks_map and groups_map schemas with patternProperties

Both maps use patternProperties + additionalProperties: false.
The tasks pattern enforces the runtime "letter or underscore first"
rule (tighter than the existing _TASK_NAME_PATTERN). The groups
pattern is imported from config/partition.py:_GROUP_NAME_PATTERN
(Task 1) so there's one source of truth.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: Root schema assembly in `build_schema()`

**Files:**

- Modify: `poethepoet/schema/generator.py`
- Modify: `tests/schema/test_smoke.py` (extend with structural assertions)

**Why:** The orchestrator walks `ProjectConfig.ConfigOptions`, translates each field, swaps in `$ref` references for the cross-cutting compositions (env, envfile, executor, tasks, groups, includes), and assembles the root schema with `$schema`, `$id`, `$comment`, `title`, `description`, `type`, `additionalProperties`, `properties`, `definitions`.

The `args` field on `TaskOptions` (NOT on the root config) also needs the `args_option` swap. This is wired through the orchestrator by registering `args_option` early so the task-variant emission picks up the ref... actually wait, the `args` field on the task-options shape is translated through the standard translator path which doesn't know about args_option. We need to swap at the property level after task-variant assembly.

Let me handle this more cleanly: after every task variant is emitted into ctx, post-process each variant's `properties.args` to be `{"$ref": "#/definitions/args_option"}`. Same for the root config's `executor` → `executor_option`, `env` → `env_option`, `envfile` → `envfile_option`. The orchestrator does these substitutions once after collecting all schemas.

- [ ] **Step 1: Add a failing structural test**

Append to `tests/schema/test_smoke.py`:

```python
def test_build_schema_has_required_root_keys() -> None:
    """The generated schema includes the standard top-level keys."""
    from poethepoet.schema import build_schema

    schema = build_schema()
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert schema["$id"] == "https://json.schemastore.org/partial-poe.json"
    assert "$comment" in schema
    assert "Generated by poethepoet" in schema["$comment"]
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "properties" in schema
    assert "definitions" in schema


def test_build_schema_root_properties_include_known_options() -> None:
    """Root-level config keys appear in properties."""
    from poethepoet.schema import build_schema

    schema = build_schema()
    expected = {
        "default_task_type", "default_array_task_type",
        "default_array_item_task_type", "env", "envfile", "executor",
        "include", "include_script", "poetry_command", "poetry_hooks",
        "shell_interpreter", "verbosity", "tasks", "groups",
    }
    assert expected.issubset(schema["properties"].keys())


def test_build_schema_definitions_include_per_task_variants() -> None:
    from poethepoet.schema import build_schema
    from poethepoet.task.base import PoeTask

    schema = build_schema()
    for key in PoeTask.get_task_types():
        assert f"{key}_task" in schema["definitions"]


def test_build_schema_env_property_refs_env_option() -> None:
    from poethepoet.schema import build_schema

    schema = build_schema()
    assert schema["properties"]["env"] == {"$ref": "#/definitions/env_option"}


def test_build_schema_tasks_property_refs_tasks_map() -> None:
    from poethepoet.schema import build_schema

    schema = build_schema()
    assert schema["properties"]["tasks"] == {"$ref": "#/definitions/tasks_map"}


def test_build_schema_executor_property_refs_executor_option() -> None:
    from poethepoet.schema import build_schema

    schema = build_schema()
    assert schema["properties"]["executor"] == {
        "$ref": "#/definitions/executor_option"
    }
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `poe test tests/schema/test_smoke.py -k "build_schema"`

Expected: FAIL — build_schema is still the placeholder from Task 3.

- [ ] **Step 3: Implement the orchestrator**

Replace the contents of `poethepoet/schema/generator.py` with:

```python
"""
Orchestrator: walks ProjectConfig.ConfigOptions and the PoeTask /
PoeExecutor registries, calls __schema_fragment__ hooks, and assembles
the complete root schema.
"""

from __future__ import annotations

from typing import Any

from poethepoet.schema.context import SchemaContext


# Properties on the root config that should reference shared definitions
# rather than inlining their translation. The translator naturally emits
# correct shapes for these from the annotations, but they're better as
# references — both for editor jump-to-definition and for not duplicating
# the schemas in the JSON file.
_ROOT_PROPERTY_REFS: dict[str, str] = {
    "env": "env_option",
    "envfile": "envfile_option",
    "executor": "executor_option",
    "tasks": "tasks_map",
    "groups": "groups_map",
}


# Properties on every task variant's options that should also $ref a
# shared definition (the same swap applied at the task level).
_TASK_PROPERTY_REFS: dict[str, str] = {
    "env": "env_option",
    "envfile": "envfile_option",
    "executor": "executor_option",
    "args": "args_option",
}


def build_schema() -> dict:
    """
    Build the complete JSON Schema for the `tool.poe` subtable.

    Returns a self-contained draft-07 schema as a dict. Stable across
    runs (sorted keys) so committed output diffs cleanly.
    """
    from poethepoet import __version__

    ctx = SchemaContext(version=__version__)

    # Build cross-cutting definitions in dependency order. task_def must
    # come before task_def_with_case (which inspects ctx.definitions for
    # the per-task variants).
    from poethepoet.schema.fragments import (
        args_option_schema,
        env_option_schema,
        envfile_option_schema,
        executor_option_schema,
        groups_map_schema,
        task_def_schema,
        task_def_with_case_schema,
        tasks_map_schema,
    )

    env_option_schema(ctx)
    envfile_option_schema(ctx)
    executor_option_schema(ctx)
    args_option_schema(ctx)
    task_def_schema(ctx)
    task_def_with_case_schema(ctx)
    tasks_map_schema(ctx)
    groups_map_schema(ctx)

    # Apply the $ref swaps inside each task variant: env, envfile,
    # executor, args.
    _apply_task_property_refs(ctx)

    # Walk ProjectConfig.ConfigOptions for the root properties.
    from poethepoet.config.partition import ProjectConfig
    from poethepoet.schema.translate import translate_type

    root_properties: dict[str, dict] = {}
    root_required: list[str] = []
    for attr_name, type_annotation in ProjectConfig.ConfigOptions.get_fields().items():
        schema_key = (
            type_annotation.metadata_get("config_name") or attr_name
        )

        # Use a $ref for cross-cutting properties.
        if schema_key in _ROOT_PROPERTY_REFS:
            ref_target = _ROOT_PROPERTY_REFS[schema_key]
            field_schema: dict[str, Any] = {
                "$ref": f"#/definitions/{ref_target}"
            }
        else:
            field_schema = translate_type(type_annotation, ctx)

        if description := ProjectConfig.ConfigOptions.description_for_field(
            attr_name
        ):
            # $ref-only schemas can't carry sibling keywords in strict
            # draft-07, but description on $ref is widely supported by
            # editors. Emit it; meta-validation is permissive.
            field_schema["description"] = description

        root_properties[schema_key] = field_schema

        # Required-ness mirrors PoeOptions.parse logic.
        has_default = hasattr(
            ProjectConfig.ConfigOptions,
            ProjectConfig.ConfigOptions.get_field_attribute(attr_name) or attr_name,
        )
        if not has_default and not type_annotation.is_optional:
            root_required.append(schema_key)

    # Assemble the root schema.
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "https://json.schemastore.org/partial-poe.json",
        "$comment": (
            f"Generated by poethepoet {ctx.version}. Do not edit by hand."
        ),
        "title": "Poe the Poet configuration",
        "description": (
            "Configuration for Poe the Poet, a task runner that works "
            "well with `pyproject.toml` files."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": sorted(root_required),
        "properties": root_properties,
        "definitions": ctx.definitions,
    }
    return schema


def _apply_task_property_refs(ctx: SchemaContext) -> None:
    """
    Walk each registered task variant in ctx.definitions and swap the
    properties listed in _TASK_PROPERTY_REFS for their corresponding
    `$ref` definitions. This must happen after all cross-cutting
    definitions (env_option, envfile_option, executor_option,
    args_option) are registered.
    """
    from poethepoet.task.base import PoeTask

    task_keys = list(PoeTask.get_task_types())
    for key in task_keys:
        for def_name in (f"{key}_task", f"{key}_task_with_case"):
            if def_name not in ctx.definitions:
                continue
            variant = ctx.definitions[def_name]
            new_properties = dict(variant["properties"])
            for prop, ref_target in _TASK_PROPERTY_REFS.items():
                if prop in new_properties:
                    new_properties[prop] = {
                        "$ref": f"#/definitions/{ref_target}"
                    }
            variant["properties"] = new_properties
```

But wait — `SchemaContext.definitions` returns a fresh dict (not a mutable view of the internal store). We need to either:
(a) Add a mutable-access method to SchemaContext, or
(b) Re-register via the existing API.

Let's go with (a) — small, principled extension. Update `SchemaContext` to expose `_definitions` via an internal accessor that the orchestrator uses (still public-ish, called `mutable_definitions` so it's a deliberate footgun).

Modify `poethepoet/schema/context.py`:

In `SchemaContext`, add after the `definitions` property:

```python
    def mutate_definition(self, name: str, schema: dict) -> None:
        """
        Replace an existing definition with a new schema body.

        This bypasses the duplicate-detection in `register` — only the
        orchestrator should use this, to apply post-hoc swaps (e.g.
        replacing inlined property schemas with $refs once cross-cutting
        definitions are available).
        """
        if name not in self._definitions:
            raise KeyError(f"No definition {name!r} to mutate")
        self._definitions[name] = schema
```

Update `_apply_task_property_refs` to use `mutate_definition`:

```python
def _apply_task_property_refs(ctx: SchemaContext) -> None:
    from poethepoet.task.base import PoeTask

    task_keys = list(PoeTask.get_task_types())
    for key in task_keys:
        for def_name in (f"{key}_task", f"{key}_task_with_case"):
            existing = ctx.definitions  # snapshot (copy)
            if def_name not in existing:
                continue
            variant = dict(existing[def_name])  # copy
            new_properties = dict(variant["properties"])
            for prop, ref_target in _TASK_PROPERTY_REFS.items():
                if prop in new_properties:
                    new_properties[prop] = {
                        "$ref": f"#/definitions/{ref_target}"
                    }
            variant["properties"] = new_properties
            ctx.mutate_definition(def_name, variant)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poe test tests/schema/test_smoke.py -k "build_schema"`

Expected: PASS.

- [ ] **Step 5: Sanity check — run all schema unit tests**

Run: `poe test tests/schema/`

Expected: All tests PASS (smoke, context, translate, fragments, schema_fragment).

- [ ] **Step 6: Commit**

```bash
git add poethepoet/schema/generator.py poethepoet/schema/context.py tests/schema/test_smoke.py
git commit -m "$(cat <<'EOF'
feat: assemble root schema in build_schema()

Walks ProjectConfig.ConfigOptions for root-level properties; calls
the cross-cutting fragment builders for env/envfile/executor/args/
task_def/tasks_map/groups_map; substitutes $refs at root and
inside each task variant so the inlined property translations get
replaced with references to the shared definitions. Adds
SchemaContext.mutate_definition for the post-hoc swap pattern.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 18: `__main__.py` writes the schema to `docs/_static/partial-poe.json`

**Files:**

- Modify: `poethepoet/schema/__main__.py`

**Why:** This is the entry point that `python -m poethepoet.schema` (and in Phase 3, `poe schema-build`) invokes. Deterministic output: sorted keys, 2-space indent, trailing newline.

- [ ] **Step 1: Write a failing test for the **main** entry point**

Create `tests/schema/test_cli.py`:

```python
"""
Tests for the `python -m poethepoet.schema` entry point.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_main_writes_partial_poe_json_to_docs(tmp_path: Path):
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
    assert result.returncode == 0, (
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    output_file = target_dir / "partial-poe.json"
    assert output_file.exists()

    # Output is valid JSON, ends with newline.
    content = output_file.read_text()
    assert content.endswith("\n")
    schema = json.loads(content)
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"


def test_main_output_is_deterministic(tmp_path: Path):
    """
    Running the CLI twice produces byte-identical output. Critical for
    the Phase 3 drift check.
    """
    target_dir = tmp_path / "docs" / "_static"
    target_dir.mkdir(parents=True)

    subprocess.run(
        [sys.executable, "-m", "poethepoet.schema"],
        cwd=tmp_path, check=True,
    )
    first = (target_dir / "partial-poe.json").read_bytes()

    subprocess.run(
        [sys.executable, "-m", "poethepoet.schema"],
        cwd=tmp_path, check=True,
    )
    second = (target_dir / "partial-poe.json").read_bytes()

    assert first == second
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `poe test tests/schema/test_cli.py`

Expected: FAIL — `__main__.py` raises SystemExit.

- [ ] **Step 3: Implement `__main__.py`**

Replace the contents of `poethepoet/schema/__main__.py` with:

```python
"""
`python -m poethepoet.schema` — regenerate docs/_static/partial-poe.json
from the current PoeOptions definitions.

Phase 3 will add a `poe schema-build` task that wraps this entry point.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from poethepoet.schema import build_schema


def main() -> int:
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poe test tests/schema/test_cli.py`

Expected: PASS.

- [ ] **Step 5: Manually generate the initial schema**

Run: `python -m poethepoet.schema`

Expected output: `Wrote docs/_static/partial-poe.json (... bytes)`.

- [ ] **Step 6: Verify the generated file looks structurally correct**

Run: `python -c "
import json
schema = json.load(open('docs/_static/partial-poe.json'))
print('Top-level keys:', sorted(schema.keys()))
print('Definitions:', sorted(schema['definitions'].keys()))
print('Properties:', sorted(schema['properties'].keys()))
print('Schema bytes:', len(open('docs/_static/partial-poe.json').read()))
"`

Expected output: lists of expected keys; size somewhere in the 1000–2000 lines range when pretty-printed.

- [ ] **Step 7: Commit**

```bash
git add poethepoet/schema/__main__.py docs/_static/partial-poe.json tests/schema/test_cli.py
git commit -m "$(cat <<'EOF'
feat: __main__ entry point + initial generated partial-poe.json

`python -m poethepoet.schema` writes deterministic, sorted-key,
trailing-newline JSON to docs/_static/partial-poe.json. The committed
file is the initial output; subsequent PoeOptions changes will
regenerate it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 19: Meta-validation test — `test_meta.py`

**Files:**

- Create: `tests/schema/test_meta.py`

**Why:** The first parity test. Asserts the generated schema is itself a valid draft-07 JSON Schema (via `Draft7Validator.check_schema`), plus structural sanity checks. Auto-marked `schema` by the conftest.

- [ ] **Step 1: Write the meta-validation tests**

Create `tests/schema/test_meta.py`:

```python
"""
Meta-validation: the generated schema is itself a valid JSON Schema
draft-07, and has the structural properties we expect at the root.
"""

from __future__ import annotations

from jsonschema import Draft7Validator

from poethepoet.schema import build_schema


def test_generated_schema_is_valid_draft7() -> None:
    """
    Run the meta-schema check from jsonschema. Catches malformed schemas
    that would break editor tooling.
    """
    schema = build_schema()
    Draft7Validator.check_schema(schema)


def test_root_has_required_top_level_keys() -> None:
    schema = build_schema()
    for key in (
        "$schema", "$id", "$comment", "title", "description",
        "type", "additionalProperties", "properties", "definitions",
    ):
        assert key in schema, f"Missing top-level key: {key}"


def test_root_additional_properties_false() -> None:
    schema = build_schema()
    assert schema["additionalProperties"] is False


def test_every_definition_is_a_valid_subschema() -> None:
    """
    Each entry in `definitions` should itself be a valid JSON Schema
    fragment (objects, arrays, refs, etc.).
    """
    schema = build_schema()
    for name, definition in schema["definitions"].items():
        # The full schema is already validated above; a soft assertion
        # at the per-definition level catches accidental malformed entries.
        assert isinstance(definition, dict), f"Definition {name!r} is not a dict"


def test_no_dangling_refs() -> None:
    """
    Every $ref in the schema points at an existing entry in definitions.
    """
    schema = build_schema()
    defined_names = set(schema["definitions"].keys())
    dangling = _collect_dangling_refs(schema, defined_names)
    assert not dangling, f"Dangling refs: {sorted(dangling)}"


def _collect_dangling_refs(node, defined_names: set[str]) -> set[str]:
    """Walk the schema and return any $ref targets not in defined_names."""
    dangling: set[str] = set()
    if isinstance(node, dict):
        if (ref := node.get("$ref")):
            assert ref.startswith("#/definitions/"), (
                f"Unexpected $ref shape: {ref!r}"
            )
            name = ref[len("#/definitions/"):]
            if name not in defined_names:
                dangling.add(name)
        for value in node.values():
            dangling.update(_collect_dangling_refs(value, defined_names))
    elif isinstance(node, list):
        for item in node:
            dangling.update(_collect_dangling_refs(item, defined_names))
    return dangling
```

- [ ] **Step 2: Run the tests**

Run: `poe test tests/schema/test_meta.py -m schema`

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/schema/test_meta.py
git commit -m "$(cat <<'EOF'
test: meta-validation of generated partial-poe.json schema

Asserts the generated schema is a valid draft-07 JSON Schema, has the
expected top-level keys, has additionalProperties: false at root, and
contains no dangling $refs. First parity test in the suite.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 20: Fixture config validation test — `test_fixture_configs.py`

**Files:**

- Create: `tests/schema/test_fixture_configs.py`

**Why:** For every `tests/fixtures/*_project/` config (pyproject.toml or poe_tasks.toml), assert the generated schema accepts the `[tool.poe]` block. Catches gaps where the runtime parses a config that the schema would reject.

- [ ] **Step 1: Write the fixture-validation test**

Create `tests/schema/test_fixture_configs.py`:

```python
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
    return Draft7Validator(build_schema())


@pytest.mark.parametrize(
    "test_id, config_path",
    _discover_fixture_configs(),
    ids=[name for name, _ in _discover_fixture_configs()],
)
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
```

- [ ] **Step 2: Run the tests**

Run: `poe test tests/schema/test_fixture_configs.py -m schema`

Expected: most/all PASS. Some may fail; that's the value of the test — it tells us where the schema is too strict.

- [ ] **Step 3: Investigate any failures**

For each failure, the test message shows the path and error. Decide per-case:

- If the schema is wrong: fix the relevant fragment / hook / translator.
- If the fixture is wrong (i.e. the runtime would also reject it in strict mode): note it as an `xfail` with a TODO comment.
- If it's a known runtime-only rule that JSON Schema can't express: same — `xfail` with a clear `reason=` indicating which spec section calls it out (Section 7 of the design doc).

Apply fixes iteratively. After each fix, regenerate the schema (`python -m poethepoet.schema`) and rerun the test.

- [ ] **Step 4: Regenerate the schema if it changed**

If any schema fixes landed in Step 3:

```bash
python -m poethepoet.schema
git add docs/_static/partial-poe.json
```

- [ ] **Step 5: Run the tests one more time to verify all pass (or xfail)**

Run: `poe test tests/schema/test_fixture_configs.py -m schema`

Expected: All tests PASS or are appropriately `xfail`.

- [ ] **Step 6: Commit**

```bash
git add tests/schema/test_fixture_configs.py
# Plus any schema fix files from Step 3
git commit -m "$(cat <<'EOF'
test: validate every fixture project config against generated schema

Parametrized over every tests/fixtures/*_project/ pyproject.toml and
poe_tasks.toml. Confirms the schema accepts what the runtime accepts.
Any divergences caught during initial test run were fixed in this
commit (see the per-file changes for specifics).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 21: Invalid corpus test — `test_invalid_corpus.py`

**Files:**

- Create: `tests/schema/fixtures/invalid/*.toml` (multiple files; see step 1)
- Create: `tests/schema/test_invalid_corpus.py`

**Why:** Curated invalid configs — known by the runtime to be rejected. The test asserts both: (a) the runtime raises `ConfigValidationError`, (b) the schema also produces validation errors. Both must reject; otherwise we have a parity gap.

- [ ] **Step 1: Create the invalid corpus fixtures**

Create `tests/schema/fixtures/invalid/unknown_root_option.toml`:

```toml
# expected_error: Unrecognized option 'oops_invalid'
[tool.poe]
oops_invalid = "bad"
```

Create `tests/schema/fixtures/invalid/bad_verbosity.toml`:

```toml
# expected_error: must have a value of type
[tool.poe]
verbosity = 99
```

Create `tests/schema/fixtures/invalid/bad_shell_interpreter.toml`:

```toml
# expected_error: must have a value of type
[tool.poe]
shell_interpreter = "bogus"
```

Create `tests/schema/fixtures/invalid/cmd_with_extra_keys.toml`:

```toml
# expected_error: Unrecognized option 'totally_bogus'
[tool.poe.tasks.bad]
cmd = "echo hello"
totally_bogus = true
```

Create `tests/schema/fixtures/invalid/bad_task_name.toml`:

```toml
# expected_error: Task names
[tool.poe.tasks."123bad"]
cmd = "echo hi"
```

Create `tests/schema/fixtures/invalid/empty_env_default.toml`:

```toml
# expected_error: Invalid declaration
[tool.poe.env]
MY_VAR = { default = 123 }
```

Create `tests/schema/fixtures/invalid/missing_required_arg_name.toml`:

```toml
# expected_error: missing required key: name
[tool.poe.tasks.has_args]
cmd = "echo $value"
args = [{}]
```

(The corpus should grow over time. Phase 2 ships with at least these 7.)

- [ ] **Step 2: Write the test**

Create `tests/schema/test_invalid_corpus.py`:

```python
"""
Parity: each curated invalid config in tests/schema/fixtures/invalid/
is rejected by BOTH the runtime PoeOptions parser AND the generated
schema. Both validators must reject; otherwise the schema is too lax.

Each fixture file's first line is `# expected_error: <substring>` —
the runtime's ConfigValidationError message must contain that substring.
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

from poethepoet.exceptions import ConfigValidationError
from poethepoet.schema import build_schema


REPO_ROOT = Path(__file__).resolve().parents[2]
INVALID_DIR = REPO_ROOT / "tests" / "schema" / "fixtures" / "invalid"


def _discover_invalid_fixtures() -> list[tuple[str, Path, str]]:
    """Return (test_id, path, expected_error_substring) for each fixture."""
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
        expected = first_line[len(prefix):].strip()
        results.append((fixture.stem, fixture, expected))
    return results


@pytest.fixture(scope="session")
def validator() -> Draft7Validator:
    return Draft7Validator(build_schema())


@pytest.mark.parametrize(
    "test_id, fixture_path, expected_error",
    _discover_invalid_fixtures(),
    ids=[name for name, _, _ in _discover_invalid_fixtures()],
)
def test_invalid_fixture_rejected_by_both_validators(
    test_id: str,
    fixture_path: Path,
    expected_error: str,
    validator: Draft7Validator,
) -> None:
    """
    Both runtime and schema must reject the fixture's [tool.poe] block.
    """
    raw = fixture_path.read_bytes()
    data = tomli.loads(raw.decode())
    poe_config = data.get("tool", {}).get("poe", data)

    # 1. Runtime rejects with the expected error substring.
    from poethepoet.config.partition import ProjectConfig
    with pytest.raises(ConfigValidationError) as runtime_excinfo:
        list(ProjectConfig.ConfigOptions.parse(poe_config, strict=True))
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
```

- [ ] **Step 3: Run the tests**

Run: `poe test tests/schema/test_invalid_corpus.py -m schema`

Expected: All tests PASS.

- [ ] **Step 4: If any fixture fails — investigate**

If the runtime accepts but the schema rejects, or vice versa, that's a real parity bug. Fix either:

- The fixture (if it was wrong about what's invalid)
- The schema (if the rejection should propagate)
- The expected_error annotation (if the wording changed)

If the schema has trouble rejecting something (e.g., a constraint JSON Schema literally can't express), `xfail` the test with a clear reason.

- [ ] **Step 5: Commit**

```bash
git add tests/schema/fixtures/invalid/ tests/schema/test_invalid_corpus.py
git commit -m "$(cat <<'EOF'
test: curated invalid-config corpus with parity assertions

Seven initial fixtures cover unknown root options, bad verbosity,
bad shell interpreter, extra keys on a cmd task, malformed task
names, malformed env_default, and missing arg fields. Each asserts
both the runtime AND the schema reject — gaps surface as
parity-bug test failures. Corpus is intended to grow.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 22: Mutation testing — `test_mutation.py`

**Files:**

- Create: `tests/schema/fixtures/seeds/*.toml`
- Create: `tests/schema/test_mutation.py`

**Why:** The strongest confidence story. Take a valid config, mutate one field, assert both validators agree on accept/reject. Catches the cases we didn't write explicit tests for.

Each (seed × mutator × applicable path) becomes its own parametrized test case, so a single divergence shows up as a single failing pytest item with a clear ID — not as one line in a multi-line failure dump. Known-divergent cases (cross-task rules the schema can't express) are wrapped in `pytest.param(..., marks=pytest.mark.xfail(reason=...))` with explicit reasons citing the relevant spec section.

Mutator library (small first pass; grow as gaps surface):

1. `mutator_delete_field` — drop a key from an object
2. `mutator_replace_str_with_int` — replace a string value with an integer (type violation)
3. `mutator_add_unexpected_key` — add a property to an object with additionalProperties:false

- [ ] **Step 1: Create seed configs**

Create `tests/schema/fixtures/seeds/simple.toml`:

```toml
[tool.poe.tasks]
hello = "echo hi"
build = { cmd = "make build", help = "Build the project" }
```

Create `tests/schema/fixtures/seeds/executors.toml`:

```toml
[tool.poe]
executor = { type = "poetry" }
verbosity = 1

[tool.poe.tasks.test]
cmd = "pytest"
```

Create `tests/schema/fixtures/seeds/complex.toml`:

```toml
[tool.poe.env]
PYTHONPATH = "src"
LOG_LEVEL = { default = "info" }

[tool.poe.tasks]
clean = "rm -rf dist build"
build = { script = "build:main", help = "Run the build" }
publish = ["build", "clean"]

[tool.poe.tasks.deploy]
shell = "deploy.sh"
deps = ["build"]
```

- [ ] **Step 2: Write the mutation tests**

Create `tests/schema/test_mutation.py`:

```python
"""
Mutation testing: load each seed config, apply each mutator at every
applicable path, and verify that the schema validator and the runtime
parser agree on accept/reject.

Each (seed × mutator × path) combination is a separate parametrized
test case so divergences are individually visible. Known runtime-only
rules — constraints JSON Schema literally can't express — are wrapped
in pytest.param(..., marks=pytest.mark.xfail(reason=...)) so they stay
visibly tracked rather than silently skipped.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator

from poethepoet.config.partition import ProjectConfig
from poethepoet.exceptions import ConfigValidationError
from poethepoet.schema import build_schema

# Match the project-wide pattern (tests/conftest.py:21-25) — `tomllib`
# is stdlib only in Python 3.11+, but the project supports 3.10.
try:
    import tomllib as tomli
except ImportError:
    import tomli  # type: ignore[no-redef]


REPO_ROOT = Path(__file__).resolve().parents[2]
SEEDS_DIR = REPO_ROOT / "tests" / "schema" / "fixtures" / "seeds"


# --- Mutators ---

Mutator = Callable[[dict, list], dict]


def _resolve(node: Any, path: list) -> Any:
    for part in path:
        node = node[part]
    return node


def _set(node: Any, path: list, value: Any) -> None:
    *prefix, last = path
    target = _resolve(node, prefix)
    target[last] = value


def mutator_delete_field(config: dict, path: list) -> dict:
    """Delete the field at path."""
    mutated = copy.deepcopy(config)
    *prefix, last = path
    target = _resolve(mutated, prefix)
    del target[last]
    return mutated


def mutator_replace_str_with_int(config: dict, path: list) -> dict:
    """Replace a string value with an integer (type violation)."""
    mutated = copy.deepcopy(config)
    if not isinstance(_resolve(mutated, path), str):
        raise ValueError("Not a string field")
    _set(mutated, path, 12345)
    return mutated


def mutator_add_unexpected_key(config: dict, path: list) -> dict:
    """Add an unexpected property to the object at path."""
    mutated = copy.deepcopy(config)
    target = _resolve(mutated, path)
    if not isinstance(target, dict):
        raise ValueError("Not a dict")
    target["__totally_bogus_key__"] = "should not be accepted"
    return mutated


MUTATORS: list[Mutator] = [
    mutator_delete_field,
    mutator_replace_str_with_int,
    mutator_add_unexpected_key,
]


# --- Path enumeration ---

def _iter_paths(node: Any, prefix: list) -> Iterator[list]:
    """Yield every path into a config (lists and dicts both descended)."""
    if isinstance(node, dict):
        for key, value in node.items():
            sub_path = prefix + [key]
            yield sub_path
            yield from _iter_paths(value, sub_path)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            sub_path = prefix + [index]
            yield sub_path
            yield from _iter_paths(item, sub_path)


# --- Validator helpers ---

def _runtime_accepts(config: dict) -> bool:
    """Returns True iff PoeOptions.parse accepts this config in strict mode."""
    try:
        list(ProjectConfig.ConfigOptions.parse(config, strict=True))
        return True
    except ConfigValidationError:
        return False


def _schema_accepts(validator: Draft7Validator, config: dict) -> bool:
    """Returns True iff the schema accepts this config."""
    return not list(validator.iter_errors(config))


@pytest.fixture(scope="session")
def validator() -> Draft7Validator:
    return Draft7Validator(build_schema())


# --- Seed discovery ---

def _discover_seeds() -> list[tuple[str, Path]]:
    return [(p.stem, p) for p in sorted(SEEDS_DIR.glob("*.toml"))]


def _load_seed(seed_path: Path) -> dict:
    data = tomli.loads(seed_path.read_text())
    return data.get("tool", {}).get("poe", data)


# --- Per-case xfail allowlist ---
#
# Maps (seed_id, mutator_name, "/"-joined path) to an xfail reason.
# Each entry must include a comment citing the spec section that
# explains WHY the schema can't enforce the rule the runtime does.
#
# Empty in the first pass; populate during execution as parity gaps
# surface. Cite spec §7 ("Cross-cutting runtime rules aren't
# expressible in JSON Schema") in each reason.
KNOWN_RUNTIME_ONLY_MISMATCHES: dict[tuple[str, str, str], str] = {
    # Example entry shape — uncomment and adapt during execution:
    # ("complex", "mutator_delete_field", "tasks/deploy/deps/0"): (
    #     "spec §7: schema cannot enforce deps reference an existing task"
    # ),
}


# --- Test-case collection ---

def _path_id(path: list) -> str:
    """Render a path list as a stable, human-readable ID component."""
    return "/".join(str(part) for part in path) or "<root>"


def _collect_mutation_cases() -> list:
    """
    Walk every seed × mutator × path combination, producing a list of
    pytest.param entries. Cases where the mutator isn't applicable at a
    given path are filtered out. Known-runtime-only mismatches are
    pre-marked xfail.
    """
    cases: list = []
    for seed_id, seed_path in _discover_seeds():
        try:
            poe_config = _load_seed(seed_path)
        except Exception as exc:  # pragma: no cover — seed corpus is curated
            raise RuntimeError(f"Failed to load seed {seed_id}") from exc

        for path in _iter_paths(poe_config, []):
            for mutator in MUTATORS:
                try:
                    mutated = mutator(poe_config, path)
                except (ValueError, KeyError, TypeError):
                    # Mutator not applicable at this path (e.g. trying
                    # to int-ify a non-string field). Skip silently.
                    continue

                test_id = f"{seed_id}-{mutator.__name__}-{_path_id(path)}"
                xfail_key = (seed_id, mutator.__name__, _path_id(path))

                marks: list = []
                if (reason := KNOWN_RUNTIME_ONLY_MISMATCHES.get(xfail_key)):
                    marks.append(pytest.mark.xfail(reason=reason, strict=True))

                cases.append(
                    pytest.param(mutated, id=test_id, marks=marks)
                )
    return cases


# --- Tests ---

@pytest.mark.parametrize(
    "seed_id, seed_path",
    _discover_seeds(),
    ids=[name for name, _ in _discover_seeds()],
)
def test_seed_baseline_validates(
    seed_id: str, seed_path: Path, validator: Draft7Validator
) -> None:
    """Every seed config is accepted by both validators (baseline)."""
    poe_config = _load_seed(seed_path)
    assert _runtime_accepts(poe_config), (
        f"Seed {seed_id} is rejected by the runtime — pick a different seed."
    )
    assert _schema_accepts(validator, poe_config), (
        f"Seed {seed_id} is rejected by the schema — schema is too strict."
    )


@pytest.mark.parametrize("mutated_config", _collect_mutation_cases())
def test_mutation_produces_validator_agreement(
    mutated_config: dict, validator: Draft7Validator
) -> None:
    """
    For each (seed × mutator × path), the schema validator and the
    runtime parser must agree on accept/reject.

    xfail-marked cases (cross-task rules) are tracked via
    KNOWN_RUNTIME_ONLY_MISMATCHES with strict=True, so an xfail entry
    that starts passing (i.e. the schema *can* express the rule now)
    surfaces as XPASS → test failure, prompting cleanup.
    """
    runtime_ok = _runtime_accepts(mutated_config)
    schema_ok = _schema_accepts(validator, mutated_config)
    assert runtime_ok == schema_ok, (
        f"Validators disagree: runtime={runtime_ok}, schema={schema_ok}. "
        f"If this rule can't be expressed in JSON Schema, add the test ID "
        f"to KNOWN_RUNTIME_ONLY_MISMATCHES with a spec-citing reason."
    )
```

- [ ] **Step 3: Run the tests**

Run: `poe test tests/schema/test_mutation.py -m schema -v`

Expected: each (seed × mutator × applicable path) appears as its own pytest item. Baselines PASS; mutation cases PASS (or XFAIL if listed in `KNOWN_RUNTIME_ONLY_MISMATCHES`).

- [ ] **Step 4: If any mutation case fails**

Each failure is a single pytest item with a clear ID like `complex-mutator_delete_field-tasks/deploy/deps/0`. Decide per-case:

- **Schema too lax (runtime rejects, schema accepts)** → fix the schema by tightening the relevant fragment / hook / translator. Regenerate `partial-poe.json`. The test will pass on the next run.
- **Schema too strict (runtime accepts, schema rejects)** → fix the schema by loosening the constraint.
- **Runtime rule not expressible in JSON Schema** → add an entry to `KNOWN_RUNTIME_ONLY_MISMATCHES`. The key is `(seed_id, mutator_name, "/"-joined-path)` — extract these three values from the failing test ID (split on `-`). The value is a short string explaining WHY, citing the relevant spec section.

Example entry to add when a `deps` mutation case fails:

```python
KNOWN_RUNTIME_ONLY_MISMATCHES: dict[tuple[str, str, str], str] = {
    ("complex", "mutator_delete_field", "tasks/deploy/deps/0"): (
        "spec §7: schema cannot enforce that deps reference an existing task"
    ),
}
```

The `strict=True` flag on `pytest.mark.xfail` ensures that if a tracked mismatch later starts agreeing (e.g. the schema is tightened enough), the test surfaces as XPASS — a failure — prompting the maintainer to remove the obsolete allowlist entry.

- [ ] **Step 5: Regenerate the schema if needed**

If any schema fixes landed:

```bash
python -m poethepoet.schema
git add docs/_static/partial-poe.json
```

- [ ] **Step 6: Re-run the full schema test suite**

Run: `poe test tests/schema/ -m schema`

Expected: All tests PASS.

- [ ] **Step 7: Run the entire project test suite to verify no regressions**

Run: `poe test`

Expected: All tests PASS (the schema marker is excluded from default test runs only after Phase 3; during Phase 2 development, schema tests run too).

Run: `poe types`

Expected: PASS — no mypy errors.

Run: `poe lint`

Expected: PASS — no lint errors.

- [ ] **Step 8: Final commit**

```bash
git add tests/schema/fixtures/seeds/ tests/schema/test_mutation.py
# Plus any schema fix files / regenerated partial-poe.json
git commit -m "$(cat <<'EOF'
test: mutation testing for runtime/schema validator parity

Three seed configs × three mutators × every applicable path = roughly
a hundred parametrized mutation cases per run. Each case is an
independent pytest item, so divergences surface individually rather
than as one line in a multi-line failure dump. Known runtime-only
rules are tracked in KNOWN_RUNTIME_ONLY_MISMATCHES (a per-case xfail
allowlist with strict=True so obsolete entries surface as XPASS).

Closes Phase 2 of the JSON Schema generation work — the generator,
hook protocol, and parity test suite are now in place. Phase 3
(lifecycle integration: poe schema-build, CI drift check, poe
test-schema) is a separate plan.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Wrap-up

After Task 22, the Phase 2 work is complete:

- `poethepoet/schema/` package generates `docs/_static/partial-poe.json` deterministically from PoeOptions definitions.
- The schema is a self-contained draft-07 JSON Schema with definitions for every task type, executor type, env/envfile/args polymorphism, and the tasks/groups maps.
- The forward-compat fallback branch in `task_def` lets editors accept dicts with unknown task-type keys.
- Parity is enforced by four test categories: meta-validation, fixture-config validation, curated invalid corpus, mutation testing.
- All Phase 2 tests live under `tests/schema/` with parity tests auto-marked `schema` so Phase 3 can wire `poe test-schema`.

**Open follow-ups for Phase 3 (separate plan):**

- `poe schema-build` task definition
- CI drift check (`poe schema-build && git diff --exit-code docs/_static/partial-poe.json`)
- `poe test-schema` task with `pytest -m schema`
- Update `poe test` to exclude the schema marker
- Update `poe test-quick` to exclude the schema marker
- Update `poe check` composition
