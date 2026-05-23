# JSON Schema Generation — Phase 1: PoeOptions cleanup & annotation expressivity

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `PoeOptions` more declarative so Phase 2's schema generator can read most of what it needs directly from annotations — Literal-tighten runtime-validated string options, extend `Metadata` with constraint fields that serve both runtime validation and schema generation, add class-attribute docstring extraction.

**Architecture:** Extend the existing `poethepoet.options.annotations.Metadata` class with new optional fields (`pattern`, `examples`, `minimum`, `maximum`, `min_length`, `max_length`). Each new constraint is enforced at parse time inside the relevant `TypeAnnotation.validate` method, so a future schema generator emitting the corresponding JSON Schema constraint reflects a real runtime rule. Class-attribute docstrings are extracted via the stdlib `ast` module (lazy-imported, cached per class) and exposed via a new `PoeOptions.description_for_field()` classmethod.

**Tech Stack:** Python 3.9+, pytest, `ast` (stdlib), `re` (stdlib). No new runtime dependencies.

**Spec reference:** `docs/superpowers/specs/2026-05-17-poe-jsonschema-generation-design.md` Section 4.

**Out of scope for this plan:** the schema generator package, schema tests, the `poe build-schema` task, CI drift checks. Those land in Phase 2 and Phase 3.

---

## Files touched

**New files:**
- `poethepoet/options/_docstrings.py` — internal helpers for AST-based class-attribute docstring extraction.
- `tests/options/test_metadata_constraints.py` — tests for the new `Metadata` constraint fields.
- `tests/options/test_descriptions.py` — tests for `PoeOptions.description_for_field()`.

**Modified files:**
- `poethepoet/options/annotations.py` — extend `Metadata`; add new constraint enforcement in `PrimitiveType.validate` and `ListType.validate`.
- `poethepoet/options/base.py` — add `PoeOptions.description_for_field()` classmethod.
- `poethepoet/config/partition.py` — introduce `ShellInterpreter` Literal type alias; rebuild `KNOWN_SHELL_INTERPRETERS` from it; tighten `ProjectConfig.ConfigOptions.shell_interpreter`; remove bespoke validation.
- `poethepoet/task/shell.py` — tighten `ShellTask.TaskOptions.interpreter`; remove bespoke validation.
- `poethepoet/task/base.py`, `poethepoet/task/cmd.py`, `poethepoet/task/shell.py`, `poethepoet/task/sequence.py`, `poethepoet/task/parallel.py`, `poethepoet/task/ref.py`, `poethepoet/task/script.py`, `poethepoet/task/expr.py`, `poethepoet/task/switch.py`, `poethepoet/task/args.py`, `poethepoet/executor/base.py`, `poethepoet/executor/uv.py`, `poethepoet/executor/virtualenv.py`, `poethepoet/config/partition.py`, `poethepoet/config/primitives.py` — backfill class-attribute docstrings on `PoeOptions`-derived fields, sourcing from the existing schemastore `partial-poe.json` where applicable.
- `CLAUDE.md` — document the class-attribute docstring convention.

---

### Task 1: Add `register_type_alias` helper and `ShellInterpreter` Literal type alias

**Files:**
- Modify: `poethepoet/options/annotations.py:18-27` (helpers near `option_annotation`)
- Modify: `poethepoet/config/partition.py:20-29` (replace `KNOWN_SHELL_INTERPRETERS`)

- [ ] **Step 1: Read the current state**

Run: `sed -n '18,30p' poethepoet/options/annotations.py` and `sed -n '1,30p' poethepoet/config/partition.py`

Confirm `annotations.py` lines 18–27 contain:

```python
T = TypeVar("T", bound=Any)
_registered_type_hint_globals = {}


def option_annotation(cls: T) -> T:
    """
    Register custom types (e.g. TypedDicts) to be usable in PoeOptions fields
    """
    _registered_type_hint_globals[cls.__name__] = cls
    return cls
```

Confirm `partition.py` lines 20–29 currently read:

```python
KNOWN_SHELL_INTERPRETERS = (
    "posix",
    "sh",
    "bash",
    "zsh",
    "fish",
    "pwsh",  # powershell >= 6
    "powershell",  # any version of powershell
    "python",
)
```

- [ ] **Step 2: Add `register_type_alias` helper**

In `poethepoet/options/annotations.py`, immediately after the `option_annotation` function (around line 27), add:

```python
def register_type_alias(name: str, type_alias: Any) -> Any:
    """
    Register a named type alias (e.g. a Literal) so it can be referenced
    by name in PoeOptions field annotations.

    Use this for type aliases that have no `__name__` (Literals, Unions, etc.)
    so they can't be registered via `option_annotation`. Class-like types
    should use `option_annotation` instead.

    Returns the type unchanged, so it can be used inline at the definition site:

        MyAlias = register_type_alias("MyAlias", Literal["a", "b", "c"])
    """

    _registered_type_hint_globals[name] = type_alias
    return type_alias
```

- [ ] **Step 3: Write a sanity test for the helper**

Append to `tests/options/test_options.py` (the existing test file):

```python
def test_register_type_alias_makes_literal_resolvable_in_annotations():
    """Verify that an alias registered via register_type_alias is findable
    when PoeOptions resolves annotation strings."""

    from typing import Literal

    from poethepoet.options import PoeOptions
    from poethepoet.options.annotations import register_type_alias

    Colour = register_type_alias("Colour", Literal["red", "green", "blue"])

    class ColouredOptions(PoeOptions):
        favourite: Colour = "red"

    options = next(ColouredOptions.parse({"favourite": "green"}))
    assert options.get("favourite") == "green"

    with pytest.raises(ConfigValidationError):
        list(ColouredOptions.parse({"favourite": "yellow"}))
```

Run: `pytest tests/options/test_options.py::test_register_type_alias_makes_literal_resolvable_in_annotations -v`
Expected: FAIL (the helper doesn't exist yet — but if you implemented it in Step 2, this should PASS now).

- [ ] **Step 4: Replace `KNOWN_SHELL_INTERPRETERS` with a Literal-backed alias**

Edit `poethepoet/config/partition.py`. Extend the `typing` import on line 6 to include `get_args`:

```python
from typing import TYPE_CHECKING, Any, Literal, TypedDict, get_args
```

Find the existing import line:

```python
from ..options.annotations import option_annotation
```

and extend it to include `register_type_alias`:

```python
from ..options.annotations import option_annotation, register_type_alias
```

Then replace the existing `KNOWN_SHELL_INTERPRETERS = (...)` block (currently around lines 20–29) with:

```python
ShellInterpreter = register_type_alias(
    "ShellInterpreter",
    Literal[
        "posix",
        "sh",
        "bash",
        "zsh",
        "fish",
        "pwsh",  # powershell >= 6
        "powershell",  # any version of powershell
        "python",
    ],
)

# Derived from the Literal so the tuple and the type stay in lockstep.
KNOWN_SHELL_INTERPRETERS: tuple[str, ...] = get_args(ShellInterpreter)
```

- [ ] **Step 5: Export `ShellInterpreter` from the config package**

Edit `poethepoet/config/__init__.py`:

```python
from .config import PoeConfig
from .partition import KNOWN_SHELL_INTERPRETERS, ConfigPartition, ShellInterpreter

__all__ = [
    "KNOWN_SHELL_INTERPRETERS",
    "ConfigPartition",
    "PoeConfig",
    "ShellInterpreter",
]
```

- [ ] **Step 6: Run tests and type checker**

Run: `poe test`
Expected: PASS — no existing test should depend on the inline tuple form, and the new sanity test should pass.

Run: `poe types`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add poethepoet/options/annotations.py poethepoet/config/partition.py poethepoet/config/__init__.py tests/options/test_options.py
git commit -m "$(cat <<'EOF'
refactor: introduce ShellInterpreter Literal alias + register_type_alias

Adds register_type_alias() in options/annotations.py so type aliases
(Literals, Unions — anything without __name__) can be referenced by name
in PoeOptions field annotations. Uses it to define ShellInterpreter,
deriving KNOWN_SHELL_INTERPRETERS from get_args so the tuple and the
type stay in lockstep. Prepares for replacing bespoke runtime validation
of shell_interpreter / interpreter options with LiteralType.validate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Tighten `ShellTask.TaskOptions.interpreter` to use `ShellInterpreter`

**Files:**
- Modify: `poethepoet/task/shell.py:28-57`

- [ ] **Step 1: Locate the current code**

Run: `sed -n '28,60p' poethepoet/task/shell.py`

Confirm `TaskOptions` currently declares:

```python
class TaskOptions(PoeTask.TaskOptions):
    interpreter: str | Sequence[str] | None = None
    ignore_fail: bool | list[int] = False

    def validate(self):
        super().validate()

        from ..config import KNOWN_SHELL_INTERPRETERS as VALID_INTERPRETERS

        if (
            isinstance(self.interpreter, str)
            and self.interpreter not in VALID_INTERPRETERS
        ):
            raise ConfigValidationError(
                "Invalid value for option 'interpreter',\n"
                f"Expected one of {VALID_INTERPRETERS}"
            )

        if isinstance(self.interpreter, list):
            if len(self.interpreter) == 0:
                raise ConfigValidationError(
                    "Invalid value for option 'interpreter',\n"
                    "Expected at least one item in list."
                )
            for item in self.interpreter:
                if item not in VALID_INTERPRETERS:
                    raise ConfigValidationError(
                        f"Invalid item {item!r} in option 'interpreter',\n"
                        f"Expected one of {VALID_INTERPRETERS!r}"
                    )
```

- [ ] **Step 2: Write a failing test for the empty-list rejection**

The Literal change will handle invalid values for free (via `LiteralType.validate`), but the empty-list rejection (`len(self.interpreter) == 0`) is a separate rule that we need to preserve. Add this preservation as Metadata in Task 7 (min_length). For now, capture the current behavior so we don't lose it during refactoring.

Add to `tests/options/test_metadata_constraints.py` (file may not exist yet — create it):

```python
"""Tests for Metadata-driven runtime constraints on PoeOptions fields."""

from typing import Annotated, Sequence

import pytest

from poethepoet.exceptions import ConfigValidationError
from poethepoet.options import PoeOptions
from poethepoet.options.annotations import Metadata


# Placeholder import sentinel: this module is intentionally minimal until
# Tasks 4-7 add the corresponding Metadata fields.
def test_module_imports():
    assert Metadata is not None
```

This file gives later tasks a home. Save it.

- [ ] **Step 3: Modify `ShellTask.TaskOptions` to use the Literal**

`shell.py` already has `from __future__ import annotations` at the top, so annotations are evaluated lazily as strings. `ShellInterpreter` was registered in Task 1 via `register_type_alias`, so it's findable by `get_type_hints` through `get_type_hint_globals()` — no runtime import is needed in `shell.py`.

In `poethepoet/task/shell.py`, find the `TaskOptions` class definition (currently lines 28–57) and replace its entire body with:

```python
class TaskOptions(PoeTask.TaskOptions):
    interpreter: ShellInterpreter | Sequence[ShellInterpreter] | None = None
    ignore_fail: bool | list[int] = False
```

The `Sequence` reference in the annotation is also resolved via `get_type_hint_globals()` (it's already in there).

Delete the entire bespoke `validate()` method on `ShellTask.TaskOptions` (the rest of lines ~32–57). The runtime checks it performed are now handled by `LiteralType.validate` (for value membership) — except the "empty list" rejection, which Task 7 will restore declaratively via `min_length`. For this commit, accept that empty lists temporarily pass validation; the regression will be re-closed in Task 7.

- [ ] **Step 4: Run the relevant tests**

Run: `poe test tests/test_shell_task*.py tests/test_config*.py -v` (or the broader `poe test` if those don't exist).

Expected: PASS. Tests that exercise the bespoke validation messages may need updates — see Step 5.

- [ ] **Step 5: Update tests that asserted the old error messages**

Search for tests that asserted the old strings ("Invalid value for option 'interpreter'" etc.):

Run: `grep -rn "Invalid value for option 'interpreter'\|Invalid item .* in option 'interpreter'" tests/`

For each match, update the assertion to match the new message produced by `LiteralType.validate` (which is `Option 'interpreter' must be one of (...)` or similar — copy the exact format by reading `poethepoet/options/annotations.py:289-291`).

Run: `poe test` to confirm green.

- [ ] **Step 6: Note the empty-list regression**

Add an `xfail` test in `tests/options/test_metadata_constraints.py` to make the regression visible until Task 7:

```python
@pytest.mark.xfail(reason="Empty-list rejection for shell interpreter not yet restored; see Task 7")
def test_empty_interpreter_list_rejected():
    # Build a ShellTask config with interpreter=[] and assert it's rejected.
    from poethepoet.task.shell import ShellTask

    with pytest.raises(ConfigValidationError):
        list(ShellTask.TaskOptions.parse({"interpreter": []}))
```

- [ ] **Step 7: Commit**

```bash
git add poethepoet/task/shell.py tests/options/test_metadata_constraints.py
git commit -m "$(cat <<'EOF'
refactor: tighten ShellTask interpreter option to use Literal type

Replace the bespoke validate() override with the Literal-derived
ShellInterpreter alias, so value membership is enforced declaratively
by LiteralType.validate. Marks the empty-list-rejection rule as xfail
pending the min_length Metadata addition in a follow-up.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Tighten `ProjectConfig.ConfigOptions.shell_interpreter`

**Files:**
- Modify: `poethepoet/config/partition.py:200` and `:283-296`

- [ ] **Step 1: Locate the current declaration and validation**

Run: `sed -n '195,310p' poethepoet/config/partition.py`

Confirm:
- Line ~200: `shell_interpreter: str | Sequence[str] = "posix"`
- Lines ~283–296: a block inside `validate()` that loops over `shell_interpreter` items and rejects unknown values.

- [ ] **Step 2: Tighten the annotation**

Change the field declaration to use `ShellInterpreter`:

```python
shell_interpreter: ShellInterpreter | Sequence[ShellInterpreter] = "posix"
```

`ShellInterpreter` is defined in the same file (Task 1), so no import needed.

- [ ] **Step 3: Delete the bespoke validation block**

Find this block inside `ProjectConfig.ConfigOptions.validate` (currently lines ~283–296):

```python
# Validate shell_interpreter type
if self.shell_interpreter:
    shell_interpreter = (
        (self.shell_interpreter,)
        if isinstance(self.shell_interpreter, str)
        else self.shell_interpreter
    )
    for interpreter in shell_interpreter:
        if interpreter not in KNOWN_SHELL_INTERPRETERS:
            raise ConfigValidationError(
                f"Unsupported value {interpreter!r} for option "
                "'shell_interpreter'\n"
                f"Expected one of {KNOWN_SHELL_INTERPRETERS!r}"
            )
```

Delete it. The Literal validator handles value membership.

- [ ] **Step 4: Run tests**

Run: `poe test`
Expected: PASS. Update any tests that asserted on the old error strings (`grep -rn "Unsupported value .* for option 'shell_interpreter'" tests/` to find them).

- [ ] **Step 5: Commit**

```bash
git add poethepoet/config/partition.py tests/
git commit -m "$(cat <<'EOF'
refactor: tighten ProjectConfig shell_interpreter to use Literal type

Apply the ShellInterpreter Literal alias to the project-level
shell_interpreter option and remove the bespoke value-membership
validation; LiteralType.validate now handles it declaratively.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3.5: Audit for other runtime-validated-against-static-list candidates

The spec calls for an audit pass to find other options that could move from bespoke runtime validation to a `Literal[...]` annotation. Shell interpreters are the obvious one (handled in Tasks 1–3); this step finds anything else.

**Files:** investigation only (no code changes if nothing's found).

- [ ] **Step 1: Grep for the typical "validated against a fixed tuple" pattern**

Run:

```bash
grep -rnE "if .* not in [A-Z_][A-Z_0-9]+" poethepoet --include="*.py" | grep -v __pycache__
```

This finds bespoke value-membership checks against module-level constants. For each match, judge whether:
- The constant is a static, exhaustive list (a candidate for `Literal[...]`), AND
- The field being checked is annotated as plain `str` (not already a Literal)

Note any candidate. Also worth scanning `validate()` overrides for hand-written enum checks that don't use a named constant.

- [ ] **Step 2: Decide and act**

If you find candidates, apply the same transformation as Tasks 1–3: define a Literal alias via `register_type_alias`, tighten the field annotation, delete the bespoke validation. Commit each transformation separately.

If nothing else qualifies (likely outcome, since shell interpreters are the main case), record this in the commit log of Task 4 or here — no code change needed. The audit is documented as completed.

- [ ] **Step 3: If changes were made, run tests**

Run: `poe test && poe types`
Expected: PASS.

---

### Task 4: Add `Metadata.pattern` with runtime enforcement

**Files:**
- Modify: `poethepoet/options/annotations.py:30-35` (Metadata class) and `:383-394` (PrimitiveType.validate)
- Test: `tests/options/test_metadata_constraints.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/options/test_metadata_constraints.py`:

```python
class PatternedOptions(PoeOptions):
    name: Annotated[str, Metadata(pattern=r"^[a-z]+$")]


def test_pattern_accepts_matching_value():
    options = next(PatternedOptions.parse({"name": "hello"}))
    assert options.get("name") == "hello"


def test_pattern_rejects_non_matching_value():
    with pytest.raises(ConfigValidationError) as exc_info:
        list(PatternedOptions.parse({"name": "Hello"}))
    # Error message must name the field and quote the pattern
    msg = str(exc_info.value)
    assert "name" in msg
    assert "^[a-z]+$" in msg


def test_pattern_uses_unanchored_search():
    """JSON Schema 'pattern' semantics are unanchored (re.search), so a
    pattern without ^/$ should match if the substring appears anywhere."""

    class SubstringPatternOptions(PoeOptions):
        token: Annotated[str, Metadata(pattern=r"[0-9]+")]

    options = next(SubstringPatternOptions.parse({"token": "abc123def"}))
    assert options.get("token") == "abc123def"

    with pytest.raises(ConfigValidationError):
        list(SubstringPatternOptions.parse({"token": "no digits here"}))


def test_pattern_not_checked_when_type_is_wrong():
    """If the value isn't a string, the pattern check is skipped (type
    error is reported instead)."""
    with pytest.raises(ConfigValidationError) as exc_info:
        list(PatternedOptions.parse({"name": 123}))
    msg = str(exc_info.value)
    assert "str" in msg or "string" in msg  # type error, not pattern error
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/options/test_metadata_constraints.py -v`
Expected: FAIL — `Metadata` does not accept `pattern` keyword argument.

- [ ] **Step 3: Extend `Metadata`**

In `poethepoet/options/annotations.py`, replace the `Metadata` class definition (currently lines 30–34):

```python
class Metadata:
    __slots__ = ("config_name", "pattern")

    def __init__(
        self,
        *,
        config_name: str | None = None,
        pattern: str | None = None,
    ):
        self.config_name = config_name
        self.pattern = pattern
```

- [ ] **Step 4: Enforce `pattern` in `PrimitiveType.validate`**

Replace the `PrimitiveType` class definition (currently lines 383–394) with:

```python
class PrimitiveType(TypeAnnotation):
    def __str__(self):
        return self._annotation.__name__

    def zero_value(self) -> Any:
        return self._annotation()

    def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
        if not isinstance(value, self._annotation):
            yield (
                f"Option {self._format_path(path)!r} must have a value of type: {self}"
            )
            return

        if self._annotation is str and self._metadata is not None:
            if (pattern := getattr(self._metadata, "pattern", None)) is not None:
                import re

                if re.search(pattern, value) is None:
                    yield (
                        f"Option {self._format_path(path)!r} value {value!r} "
                        f"does not match pattern {pattern!r}"
                    )
```

Note the `import re` is inline / lazy: `re` is part of stdlib so the cost is negligible, but this keeps the import close to its use.

- [ ] **Step 5: Run tests to confirm they pass**

Run: `pytest tests/options/test_metadata_constraints.py -v`
Expected: PASS — all four pattern tests.

Run: `poe test`
Expected: PASS — no regression in the existing suite.

- [ ] **Step 6: Commit**

```bash
git add poethepoet/options/annotations.py tests/options/test_metadata_constraints.py
git commit -m "$(cat <<'EOF'
feat: add pattern field to PoeOptions Metadata

Adds a regex pattern constraint that, when attached via Annotated[str,
Metadata(pattern=...)], is enforced at parse time inside
PrimitiveType.validate. Uses re.search (unanchored) to match JSON Schema
'pattern' semantics. Validation messages name the field, the offending
value, and the pattern.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Add `Metadata.examples` (documentation-only)

**Files:**
- Modify: `poethepoet/options/annotations.py:30-40` (Metadata class)
- Test: `tests/options/test_metadata_constraints.py`

- [ ] **Step 1: Write failing test**

Append to `tests/options/test_metadata_constraints.py`:

```python
def test_examples_stored_on_metadata():
    """examples is documentation-only — no runtime validation, just preserved
    for downstream consumers (the schema generator)."""

    class ExampledOptions(PoeOptions):
        path: Annotated[
            str, Metadata(examples=["output.log", "${POE_PWD}/output.txt"])
        ] = ""

    # Should parse without complaint.
    options = next(ExampledOptions.parse({"path": "anything"}))
    assert options.get("path") == "anything"

    # The Metadata object is accessible through the field's TypeAnnotation:
    annotation = ExampledOptions.get_fields()["path"]
    examples = annotation.metadata_get("examples")
    assert examples == ["output.log", "${POE_PWD}/output.txt"]
```

- [ ] **Step 2: Run test to confirm failure**

Run: `pytest tests/options/test_metadata_constraints.py::test_examples_stored_on_metadata -v`
Expected: FAIL — `Metadata` does not accept `examples` keyword argument.

- [ ] **Step 3: Extend `Metadata`**

In `poethepoet/options/annotations.py`, update `Metadata` to include `examples`:

```python
class Metadata:
    __slots__ = ("config_name", "pattern", "examples")

    def __init__(
        self,
        *,
        config_name: str | None = None,
        pattern: str | None = None,
        examples: list | None = None,
    ):
        self.config_name = config_name
        self.pattern = pattern
        self.examples = examples
```

No runtime validation logic to add — `examples` is documentation metadata, surfaced later by the schema generator.

- [ ] **Step 4: Run test to confirm pass**

Run: `pytest tests/options/test_metadata_constraints.py::test_examples_stored_on_metadata -v`
Expected: PASS.

Run: `poe test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poethepoet/options/annotations.py tests/options/test_metadata_constraints.py
git commit -m "$(cat <<'EOF'
feat: add examples field to PoeOptions Metadata

Documentation-only field consumed by the schema generator; no runtime
validation. Mirrors the existing config_name field, which is similarly
metadata-only with no validation role.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Add `Metadata.minimum` and `Metadata.maximum` for numeric types

**Files:**
- Modify: `poethepoet/options/annotations.py` (Metadata class + PrimitiveType.validate)
- Test: `tests/options/test_metadata_constraints.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/options/test_metadata_constraints.py`:

```python
class BoundedIntOptions(PoeOptions):
    count: Annotated[int, Metadata(minimum=0, maximum=100)] = 0


def test_minimum_accepts_value_at_bound():
    options = next(BoundedIntOptions.parse({"count": 0}))
    assert options.get("count") == 0


def test_minimum_rejects_value_below_bound():
    with pytest.raises(ConfigValidationError) as exc_info:
        list(BoundedIntOptions.parse({"count": -1}))
    msg = str(exc_info.value)
    assert "count" in msg
    assert "0" in msg  # the bound


def test_maximum_accepts_value_at_bound():
    options = next(BoundedIntOptions.parse({"count": 100}))
    assert options.get("count") == 100


def test_maximum_rejects_value_above_bound():
    with pytest.raises(ConfigValidationError) as exc_info:
        list(BoundedIntOptions.parse({"count": 101}))
    msg = str(exc_info.value)
    assert "count" in msg
    assert "100" in msg


def test_bounds_apply_to_floats():
    class BoundedFloatOptions(PoeOptions):
        ratio: Annotated[float, Metadata(minimum=0.0, maximum=1.0)] = 0.5

    next(BoundedFloatOptions.parse({"ratio": 0.5}))  # in range
    next(BoundedFloatOptions.parse({"ratio": 0.0}))  # at minimum
    next(BoundedFloatOptions.parse({"ratio": 1.0}))  # at maximum
    with pytest.raises(ConfigValidationError):
        list(BoundedFloatOptions.parse({"ratio": 1.1}))


def test_bounds_not_applied_to_strings():
    """minimum/maximum apply only to numeric types; on a str field they're
    silently ignored (the schema generator would also skip them)."""

    class StringWithBoundsOptions(PoeOptions):
        # Intentionally weird combination — runtime should not crash.
        text: Annotated[str, Metadata(minimum=0, maximum=100)] = ""

    options = next(StringWithBoundsOptions.parse({"text": "hello"}))
    assert options.get("text") == "hello"
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/options/test_metadata_constraints.py -v -k "minimum or maximum or bound"`
Expected: FAIL — `Metadata` doesn't accept `minimum`/`maximum`.

- [ ] **Step 3: Extend `Metadata`**

Update `Metadata` in `poethepoet/options/annotations.py`:

```python
class Metadata:
    __slots__ = ("config_name", "pattern", "examples", "minimum", "maximum")

    def __init__(
        self,
        *,
        config_name: str | None = None,
        pattern: str | None = None,
        examples: list | None = None,
        minimum: int | float | None = None,
        maximum: int | float | None = None,
    ):
        self.config_name = config_name
        self.pattern = pattern
        self.examples = examples
        self.minimum = minimum
        self.maximum = maximum
```

- [ ] **Step 4: Enforce bounds in `PrimitiveType.validate`**

Update the body of `PrimitiveType.validate` to also check bounds:

```python
def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
    if not isinstance(value, self._annotation):
        yield (
            f"Option {self._format_path(path)!r} must have a value of type: {self}"
        )
        return

    if self._metadata is None:
        return

    if self._annotation is str:
        if (pattern := getattr(self._metadata, "pattern", None)) is not None:
            import re

            if re.search(pattern, value) is None:
                yield (
                    f"Option {self._format_path(path)!r} value {value!r} "
                    f"does not match pattern {pattern!r}"
                )

    if self._annotation in (int, float):
        if (minimum := getattr(self._metadata, "minimum", None)) is not None:
            if value < minimum:
                yield (
                    f"Option {self._format_path(path)!r} value {value!r} "
                    f"is below minimum {minimum!r}"
                )
        if (maximum := getattr(self._metadata, "maximum", None)) is not None:
            if value > maximum:
                yield (
                    f"Option {self._format_path(path)!r} value {value!r} "
                    f"is above maximum {maximum!r}"
                )
```

- [ ] **Step 5: Run tests to confirm pass**

Run: `pytest tests/options/test_metadata_constraints.py -v`
Expected: PASS.

Run: `poe test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add poethepoet/options/annotations.py tests/options/test_metadata_constraints.py
git commit -m "$(cat <<'EOF'
feat: add minimum and maximum fields to PoeOptions Metadata

Adds numeric bounds enforcement for int and float fields. When attached
via Annotated[int, Metadata(minimum=..., maximum=...)], values outside
the inclusive range are rejected at parse time. Bounds are silently
ignored on non-numeric fields.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Add `Metadata.min_length` and `Metadata.max_length`

**Files:**
- Modify: `poethepoet/options/annotations.py` (Metadata class, PrimitiveType.validate, ListType.validate)
- Modify: `poethepoet/task/shell.py` (apply min_length=1 to interpreter; remove xfail)
- Test: `tests/options/test_metadata_constraints.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/options/test_metadata_constraints.py`:

```python
def test_min_length_rejects_short_string():
    class MinLenStrOptions(PoeOptions):
        name: Annotated[str, Metadata(min_length=3)] = ""

    next(MinLenStrOptions.parse({"name": "abc"}))  # at boundary
    next(MinLenStrOptions.parse({"name": "abcd"}))  # above
    with pytest.raises(ConfigValidationError) as exc_info:
        list(MinLenStrOptions.parse({"name": "ab"}))
    assert "name" in str(exc_info.value)
    assert "3" in str(exc_info.value)


def test_max_length_rejects_long_string():
    class MaxLenStrOptions(PoeOptions):
        name: Annotated[str, Metadata(max_length=5)] = ""

    next(MaxLenStrOptions.parse({"name": "hello"}))  # at boundary
    with pytest.raises(ConfigValidationError):
        list(MaxLenStrOptions.parse({"name": "helloX"}))


def test_min_length_rejects_short_list():
    class MinLenListOptions(PoeOptions):
        items: Annotated[Sequence[str], Metadata(min_length=1)] = ()

    next(MinLenListOptions.parse({"items": ["one"]}))  # at boundary
    with pytest.raises(ConfigValidationError) as exc_info:
        list(MinLenListOptions.parse({"items": []}))
    assert "items" in str(exc_info.value)


def test_max_length_rejects_long_list():
    class MaxLenListOptions(PoeOptions):
        items: Annotated[Sequence[str], Metadata(max_length=2)] = ()

    next(MaxLenListOptions.parse({"items": ["a", "b"]}))  # at boundary
    with pytest.raises(ConfigValidationError):
        list(MaxLenListOptions.parse({"items": ["a", "b", "c"]}))
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/options/test_metadata_constraints.py -v -k "length"`
Expected: FAIL — `Metadata` doesn't accept length fields.

- [ ] **Step 3: Extend `Metadata`**

Update `Metadata` in `poethepoet/options/annotations.py`:

```python
class Metadata:
    __slots__ = (
        "config_name",
        "pattern",
        "examples",
        "minimum",
        "maximum",
        "min_length",
        "max_length",
    )

    def __init__(
        self,
        *,
        config_name: str | None = None,
        pattern: str | None = None,
        examples: list | None = None,
        minimum: int | float | None = None,
        maximum: int | float | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
    ):
        self.config_name = config_name
        self.pattern = pattern
        self.examples = examples
        self.minimum = minimum
        self.maximum = maximum
        self.min_length = min_length
        self.max_length = max_length
```

- [ ] **Step 4: Enforce length in `PrimitiveType.validate` (for str)**

Read the current `PrimitiveType.validate` first — it was last modified in Task 6 to include pattern and bounds checks. The full new version (replacing the entire `validate` method body) should be:

```python
def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
    if not isinstance(value, self._annotation):
        yield (
            f"Option {self._format_path(path)!r} must have a value of type: {self}"
        )
        return

    if self._metadata is None:
        return

    if self._annotation is str:
        if (pattern := getattr(self._metadata, "pattern", None)) is not None:
            import re

            if re.search(pattern, value) is None:
                yield (
                    f"Option {self._format_path(path)!r} value {value!r} "
                    f"does not match pattern {pattern!r}"
                )
        if (min_length := getattr(self._metadata, "min_length", None)) is not None:
            if len(value) < min_length:
                yield (
                    f"Option {self._format_path(path)!r} value {value!r} "
                    f"is shorter than minimum length {min_length}"
                )
        if (max_length := getattr(self._metadata, "max_length", None)) is not None:
            if len(value) > max_length:
                yield (
                    f"Option {self._format_path(path)!r} value {value!r} "
                    f"is longer than maximum length {max_length}"
                )

    if self._annotation in (int, float):
        if (minimum := getattr(self._metadata, "minimum", None)) is not None:
            if value < minimum:
                yield (
                    f"Option {self._format_path(path)!r} value {value!r} "
                    f"is below minimum {minimum!r}"
                )
        if (maximum := getattr(self._metadata, "maximum", None)) is not None:
            if value > maximum:
                yield (
                    f"Option {self._format_path(path)!r} value {value!r} "
                    f"is above maximum {maximum!r}"
                )
```

This is the cumulative state after Tasks 4, 6, and 7. The new additions (vs. the Task 6 version) are the two `min_length`/`max_length` blocks inside the `if self._annotation is str:` branch.

- [ ] **Step 5: Enforce length in `ListType.validate`**

In `poethepoet/options/annotations.py`, update `ListType.validate` (currently lines 259–267):

```python
def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
    if not isinstance(value, list | tuple):
        yield f"Option {self._format_path(path)!r} must be a list"
        return

    if self._metadata is not None:
        if (min_length := getattr(self._metadata, "min_length", None)) is not None:
            if len(value) < min_length:
                yield (
                    f"Option {self._format_path(path)!r} requires at least "
                    f"{min_length} item(s), got {len(value)}"
                )
        if (max_length := getattr(self._metadata, "max_length", None)) is not None:
            if len(value) > max_length:
                yield (
                    f"Option {self._format_path(path)!r} allows at most "
                    f"{max_length} item(s), got {len(value)}"
                )

    if isinstance(self._value_type, AnyType):
        return

    for idx, item in enumerate(value):
        yield from self._value_type.validate((*path, idx), item)
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/options/test_metadata_constraints.py -v`
Expected: PASS — all length tests pass.

Run: `poe test`
Expected: PASS.

- [ ] **Step 7: Apply `min_length=1` to ShellTask interpreter (restore the empty-list rejection)**

Edit `poethepoet/task/shell.py`. With `from __future__ import annotations` already at the top, the annotation is a string — `Annotated`, `ShellInterpreter`, `Sequence`, and `Metadata` are all resolved via `get_type_hint_globals()`, so no new imports are needed.

Change the `interpreter` declaration on `ShellTask.TaskOptions`:

```python
class TaskOptions(PoeTask.TaskOptions):
    interpreter: Annotated[
        ShellInterpreter | Sequence[ShellInterpreter] | None,
        Metadata(min_length=1),
    ] = None
    ignore_fail: bool | list[int] = False
```

Note that `min_length` on a union type applies only when the value is a list (since `ListType.validate` is what enforces it). A `None` value or a single-string value goes through different branches and isn't affected. This is the intended semantics: "if you provide a list, it must have at least one item."

- [ ] **Step 8: Remove the xfail marker from Task 2's empty-list test**

In `tests/options/test_metadata_constraints.py`, remove the `@pytest.mark.xfail(...)` decorator from `test_empty_interpreter_list_rejected` so it runs as a real test now.

- [ ] **Step 9: Run tests**

Run: `pytest tests/options/test_metadata_constraints.py::test_empty_interpreter_list_rejected -v`
Expected: PASS (previously xfail, now real pass).

Run: `poe test`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add poethepoet/options/annotations.py poethepoet/task/shell.py tests/options/test_metadata_constraints.py
git commit -m "$(cat <<'EOF'
feat: add min_length and max_length fields to PoeOptions Metadata

Adds length-bounds enforcement for str fields (character length) and
list/sequence fields (item count). Applies min_length=1 to ShellTask's
interpreter list option, restoring the empty-list-rejection rule that
was temporarily lost during the Literal refactor.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Implement class-attribute docstring extraction

**Files:**
- Create: `poethepoet/options/_docstrings.py`
- Modify: `poethepoet/options/base.py` (add `description_for_field` classmethod)
- Test: `tests/options/test_descriptions.py`

- [ ] **Step 1: Write failing tests**

Create `tests/options/test_descriptions.py`:

```python
"""Tests for PoeOptions.description_for_field — class-attribute docstring extraction."""

from poethepoet.options import PoeOptions


class DescribedOptions(PoeOptions):
    foo: str = ""
    """The foo field — should be discoverable."""

    bar: int = 0
    """Multi-line description
    spanning two lines."""

    baz: bool = False  # no docstring


class ChildOptions(DescribedOptions):
    foo: str = "override"
    """Overridden description for foo."""

    qux: str = ""
    """Qux on the child only."""


class GrandchildOptions(ChildOptions):
    """Class-level docstring; not a field docstring."""

    # foo is inherited from ChildOptions; description should follow MRO
    new_field: str = ""
    """A field defined only here."""


def test_description_extracted_from_simple_docstring():
    assert (
        DescribedOptions.description_for_field("foo")
        == "The foo field — should be discoverable."
    )


def test_description_extracted_from_multiline_docstring():
    description = DescribedOptions.description_for_field("bar")
    assert description is not None
    assert "Multi-line description" in description
    assert "spanning two lines" in description


def test_description_is_none_when_no_docstring():
    assert DescribedOptions.description_for_field("baz") is None


def test_description_returns_none_for_unknown_field():
    assert DescribedOptions.description_for_field("nonexistent") is None


def test_subclass_override_takes_precedence():
    assert (
        ChildOptions.description_for_field("foo")
        == "Overridden description for foo."
    )


def test_subclass_own_field_resolved():
    assert (
        ChildOptions.description_for_field("qux") == "Qux on the child only."
    )


def test_inherited_field_resolves_to_parent_docstring():
    # GrandchildOptions doesn't redeclare foo; the description should
    # come from ChildOptions (the nearest ancestor that defines it).
    assert (
        GrandchildOptions.description_for_field("foo")
        == "Overridden description for foo."
    )


def test_class_docstring_is_not_treated_as_field_description():
    # GrandchildOptions has a class docstring but it's not a field doc.
    # Looking up the first real field should still work.
    assert (
        GrandchildOptions.description_for_field("new_field")
        == "A field defined only here."
    )


def test_description_cache_is_populated_per_class():
    """The first call should populate a per-class cache."""
    # Trigger a lookup
    DescribedOptions.description_for_field("foo")
    # Cache attribute is set on the class's own __dict__ (not inherited).
    assert "_poe_field_descriptions" in DescribedOptions.__dict__
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/options/test_descriptions.py -v`
Expected: FAIL — `PoeOptions` has no `description_for_field` classmethod.

- [ ] **Step 3: Implement the AST-based extractor**

Create `poethepoet/options/_docstrings.py`:

```python
"""
Internal helpers for extracting per-field documentation from PoeOptions
class definitions.

The convention is PEP 257-style class attribute documentation:

    class MyOptions(PoeOptions):
        name: str = ""
        '''Description of the name field.'''

i.e. a string literal expression statement immediately following an
annotated assignment in the class body. Multi-line docstrings are
supported; leading/trailing whitespace is stripped from each line.

Extraction is per-class (the result is keyed by `cls.__name__` of the
declaring class, then by field name) and cached.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from functools import lru_cache


@lru_cache(maxsize=None)
def extract_field_descriptions(cls: type) -> dict[str, str]:
    """
    Parse the source of `cls` and return a mapping of field name → description
    for every annotated field whose declaration is immediately followed by a
    string-literal expression statement.

    Only fields declared directly on `cls` are returned (not inherited fields).
    The caller is responsible for MRO walking — see
    `PoeOptions.description_for_field`.
    """

    try:
        source = inspect.getsource(cls)
    except (OSError, TypeError):
        # No source available (e.g. dynamic class, REPL).
        return {}

    source = textwrap.dedent(source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    # The first node should be the ClassDef for `cls`.
    if not tree.body or not isinstance(tree.body[0], ast.ClassDef):
        return {}

    class_body = tree.body[0].body

    descriptions: dict[str, str] = {}

    for index, node in enumerate(class_body):
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        field_name = node.target.id

        # Look at the immediately following statement.
        next_index = index + 1
        if next_index >= len(class_body):
            continue
        next_node = class_body[next_index]
        if not (
            isinstance(next_node, ast.Expr)
            and isinstance(next_node.value, ast.Constant)
            and isinstance(next_node.value.value, str)
        ):
            continue

        raw = next_node.value.value
        # Normalize whitespace: strip leading/trailing blank space, dedent
        # multi-line strings, then join lines that the author wrote split
        # across the source for column-width reasons.
        descriptions[field_name] = textwrap.dedent(raw).strip()

    return descriptions
```

- [ ] **Step 4: Add `description_for_field` to `PoeOptions`**

In `poethepoet/options/base.py`, add this classmethod inside the `PoeOptions` class (after `get_field_attribute`):

```python
    @classmethod
    def description_for_field(cls, field_name: str) -> str | None:
        """
        Return the class-attribute docstring associated with the field, if any.

        Walks the MRO so that an inherited field resolves to its description
        on the nearest ancestor that defines it. Returns None if no description
        is found.

        The first call per class populates a per-class cache stored as
        `cls._poe_field_descriptions`.
        """

        from ._docstrings import extract_field_descriptions

        # Use cls.__dict__ rather than hasattr() so the cache is per-class
        # (not inherited from an ancestor that happened to compute it first).
        # Single leading underscore avoids Python's name-mangling rules.
        if "_poe_field_descriptions" not in cls.__dict__:
            merged: dict[str, str] = {}
            # Reverse MRO so subclass entries override ancestor entries.
            for ancestor in reversed(cls.__mro__):
                if ancestor is object:
                    continue
                merged.update(extract_field_descriptions(ancestor))
            cls._poe_field_descriptions = merged

        return cls._poe_field_descriptions.get(field_name)
```

The single-underscore prefix (`_poe_field_descriptions`) deliberately avoids Python's double-underscore name mangling, which would have made per-class caching subtle and error-prone. Per-class isolation is enforced by checking `cls.__dict__` directly rather than via `hasattr` (which would follow the inheritance chain).

- [ ] **Step 5: Run tests to confirm pass**

Run: `pytest tests/options/test_descriptions.py -v`
Expected: PASS — all eight tests.

Run: `poe test`
Expected: PASS — no regression.

Run: `poe types`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add poethepoet/options/_docstrings.py poethepoet/options/base.py tests/options/test_descriptions.py
git commit -m "$(cat <<'EOF'
feat: extract class-attribute docstrings for PoeOptions field descriptions

Adds PoeOptions.description_for_field(name) and supporting AST-based
extraction in options/_docstrings.py. Class-attribute docstrings follow
the PEP 257-style convention: a string literal expression statement
immediately following an annotated assignment. Lookups walk the MRO so
inherited fields resolve to the nearest ancestor that defines them.

Used by the upcoming schema generator (Phase 2) to populate JSON Schema
description fields.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Backfill PoeOptions class-attribute docstrings

**Files:**
- Modify (add docstrings to existing field declarations): `poethepoet/config/partition.py`, `poethepoet/task/base.py`, `poethepoet/task/cmd.py`, `poethepoet/task/shell.py`, `poethepoet/task/sequence.py`, `poethepoet/task/parallel.py`, `poethepoet/task/ref.py`, `poethepoet/task/script.py`, `poethepoet/task/expr.py`, `poethepoet/task/switch.py`, `poethepoet/task/args.py`, `poethepoet/executor/base.py`, `poethepoet/executor/uv.py`, `poethepoet/executor/virtualenv.py`, `poethepoet/config/primitives.py`

- [ ] **Step 1: Fetch the existing schemastore schema as reference**

Run: `curl -sL https://raw.githubusercontent.com/SchemaStore/schemastore/master/src/schemas/json/partial-poe.json -o /tmp/existing-partial-poe.json`

Open `/tmp/existing-partial-poe.json` in a viewer. For each field on each `TaskOptions` / `ConfigOptions` / `ExecutorOptions` subclass, locate the corresponding `description` string in the existing schema.

- [ ] **Step 2: Map fields to source**

For each PoeOptions class, identify every annotated field and either:
- Copy the existing schema's description verbatim into a class-attribute docstring, OR
- Write a new docstring if no existing description fits (rare).

The mapping (existing schema location → code location):

| Field | Existing schema path | Code location |
|---|---|---|
| `cwd` | `definitions.standard_options.properties.cwd.description` | `poethepoet/task/base.py` `PoeTask.TaskOptions.cwd` |
| `deps` | `definitions.standard_options.properties.deps.description` | `poethepoet/task/base.py` `PoeTask.TaskOptions.deps` |
| `env` | `definitions.standard_options.properties.env.description` (under `env_option`) | `poethepoet/task/base.py` `PoeTask.TaskOptions.env` |
| `envfile` | `definitions.envfile_option.description` | `poethepoet/task/base.py` `PoeTask.TaskOptions.envfile` |
| `executor` | `definitions.executor_option.description` | `poethepoet/task/base.py` `PoeTask.TaskOptions.executor` |
| `help` | `definitions.standard_options.properties.help.description` | `poethepoet/task/base.py` `PoeTask.TaskOptions.help` |
| `uses` | `definitions.standard_options.properties.uses.description` | `poethepoet/task/base.py` `PoeTask.TaskOptions.uses` |
| `verbosity` | `definitions.standard_options.properties.verbosity.description` | `poethepoet/task/base.py` `PoeTask.TaskOptions.verbosity` |
| `args` | `definitions.standard_options.properties.args.description` | `poethepoet/task/base.py` `PoeTask.TaskOptions.args` |
| `capture_stdout` | `definitions.capture_stdout_option.properties.capture_stdout.description` | `poethepoet/task/base.py` `PoeTask.TaskOptions.capture_stdout` |
| `use_exec` | `definitions.use_exec_option.properties.use_exec.description` | `poethepoet/task/cmd.py`, `script.py`, `expr.py` `TaskOptions.use_exec` |
| `empty_glob` | `definitions.cmd_task.properties.empty_glob.description` | `poethepoet/task/cmd.py` `CmdTask.TaskOptions.empty_glob` |
| `ignore_fail` | varies per task | each task's `TaskOptions.ignore_fail` |
| `interpreter` | `definitions.shell_task.properties.interpreter.description` | `poethepoet/task/shell.py` `ShellTask.TaskOptions.interpreter` |
| `default_item_type` | `definitions.sequence_task.properties.default_item_type.description` | `poethepoet/task/sequence.py`, `parallel.py` |
| `prefix`, `prefix_max`, `prefix_template` | `definitions.parallel_task.properties.*` | `poethepoet/task/parallel.py` |
| `print_result` | `definitions.script_task.properties.print_result.description` | `poethepoet/task/script.py` |
| `imports`, `assert` | `definitions.expr_task.properties.*` | `poethepoet/task/expr.py` |
| `control`, `default` | `definitions.switch_task.properties.*` | `poethepoet/task/switch.py` |
| `default_task_type`, `default_array_task_type`, `default_array_item_task_type` | root-level `properties.*` | `poethepoet/config/partition.py` `ProjectConfig.ConfigOptions` |
| `include`, `include_script` | root-level `properties.*` | same |
| `poetry_command`, `poetry_hooks` | root-level | same |
| `shell_interpreter` | root-level | same |
| `tasks`, `groups`, `verbosity` | root-level | same |
| `name`, `default`, `help`, `options`, `positional`, `required`, `type`, `multiple`, `choices` on `ArgSpec` | `definitions.standard_options.properties.args.definitions.args.properties.*` | `poethepoet/task/args.py` |
| `type` (executor discriminator) | `definitions.executor_*.properties.type.description` | `poethepoet/executor/base.py` `PoeExecutor.ExecutorOptions.type` |
| Each uv executor field | `definitions.executor_uv.properties.*` | `poethepoet/executor/uv.py` |
| `location` (virtualenv) | `definitions.executor_virtualenv.properties.location` | `poethepoet/executor/virtualenv.py` |

For TypedDicts (`IncludeItem`, `IncludeScriptItem`, `TaskGroup`, `EnvDefault`, `EnvfileOption`) the AST-based extractor only sees them if they're parseable — TypedDict fields can carry class-attribute docstrings the same way. Backfill these too.

- [ ] **Step 3: Apply the docstrings**

For each field, add the docstring on the line immediately after the annotation. Example (`poethepoet/task/base.py`):

```python
class TaskOptions(PoeOptions):
    args: dict | list | None = None
    """Define CLI options, positional arguments, or flags that this task should accept."""

    capture_stdout: str | None = None
    """Redirects the task output to a file with the given path. Supports environment variable interpolation."""

    cwd: str | None = None
    """Specify the current working directory that this task should run with. This can be a relative path from the project root or an absolute path, and environment variables can be used in the format ${VAR_NAME}."""

    # ... and so on for every annotated field
```

Take care to:
- Use the existing schemastore description verbatim where possible (preserves editor experience).
- Keep docstrings as PEP 257-style triple-quoted strings on the line(s) immediately after the annotation.
- For multi-line descriptions, use real line breaks inside the triple-quoted string.

- [ ] **Step 4: Verify lookup works for every annotated field**

Add a smoke test to `tests/options/test_descriptions.py`:

```python
def test_every_taskoptions_field_has_a_description():
    """Sanity check that backfill is comprehensive. Lists any field on a
    PoeTask.TaskOptions subclass that lacks a description so gaps are
    discoverable."""

    from poethepoet.task.base import PoeTask

    # Walk all registered task types
    missing: list[tuple[str, str]] = []
    for key, task_cls in PoeTask._PoeTask__task_types.items():
        options_cls = task_cls.TaskOptions
        for field_name in options_cls.get_fields():
            if options_cls.description_for_field(field_name) is None:
                missing.append((task_cls.__name__, field_name))

    assert not missing, (
        f"Found {len(missing)} TaskOptions fields without a description: "
        f"{missing!r}. Add a class-attribute docstring immediately after "
        "the annotation."
    )


def test_every_configoptions_field_has_a_description():
    from poethepoet.config.partition import ProjectConfig

    missing: list[str] = []
    for field_name in ProjectConfig.ConfigOptions.get_fields():
        if ProjectConfig.ConfigOptions.description_for_field(field_name) is None:
            missing.append(field_name)

    assert not missing, (
        f"Found ProjectConfig.ConfigOptions fields without a description: "
        f"{missing!r}. Add a class-attribute docstring."
    )
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/options/test_descriptions.py -v`
Expected: PASS — including the comprehensiveness checks.

Run: `poe test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add poethepoet/ tests/
git commit -m "$(cat <<'EOF'
docs: backfill PoeOptions field docstrings from existing schemastore entry

Add class-attribute docstrings to every annotated field on PoeOptions
subclasses (task options, executor options, config options, plus the
TypedDicts used in the option schemas). Source: the descriptions in the
current community-contributed partial-poe.json on schemastore.

Used by PoeOptions.description_for_field, which the upcoming schema
generator (Phase 2) consumes to populate JSON Schema description fields.
Tests assert comprehensiveness so future field additions don't silently
ship without descriptions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Document the docstring convention in CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read the current CLAUDE.md to find the right insertion point**

Run: `cat CLAUDE.md`

Identify the section that documents code conventions (likely under "Code style" near the bottom). The new docstring convention belongs there.

- [ ] **Step 2: Add the convention**

In `CLAUDE.md`, add the following bullet under the "Code style" section:

```markdown
- `PoeOptions` fields use class-attribute docstrings (PEP 257-style) immediately after the annotation. These are extracted by `PoeOptions.description_for_field()` and consumed by the JSON Schema generator. Every field on a `PoeOptions` subclass should have one; the description backfill tests catch gaps.

  Example:
  ```python
  class TaskOptions(PoeOptions):
      cwd: str | None = None
      """Working directory the task runs in. Relative to the project root unless absolute."""
  ```
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: document the PoeOptions class-attribute docstring convention

Notes the PEP 257-style convention used for field descriptions on
PoeOptions subclasses, so contributors adding new options know they
need to document them inline.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Scope Metadata to specific branches; add `min_items` / `max_items`

**Files:**
- Modify: `poethepoet/options/annotations.py` (Metadata class, UnionType, ListType)
- Modify: `poethepoet/task/shell.py:31-35` (move Metadata from union to list branch; rename `min_length` → `min_items`)
- Test: `tests/options/test_metadata_constraints.py` (new tests for nested-Annotated parsing, propagation removal, `min_items`/`max_items`, `type_constraints()`)

**Background:** Spec Section 4 documents the design intent: `Metadata` has two scopes (field-level and type-level), type-level constraints attach to the specific branch via `Annotated[T, Metadata(...)]`, and `UnionType` does not propagate metadata into its children. The implementation in Tasks 1–10 took a shortcut — `UnionType._wrap_with_metadata` pushed the outer metadata into every child — which works for the one current production callsite (`Sequence[ShellInterpreter]` happens to be the only branch that reads `min_length`) but creates a foot-gun for any future `str | list[str]` field where `min_length` would mean two different things. This task closes that gap.

The task is TDD-style: write the failing tests for the intended semantics first, then implement. Some test cases exercise constraint shapes that don't appear in production code today — that's deliberate, since real usage isn't yet broad enough to surface the API surface.

- [ ] **Step 1: Write failing test for nested-Annotated parsing**

In `tests/options/test_metadata_constraints.py` (built up across Tasks 2–7), expand the existing `from poethepoet.options.annotations import Metadata` line to also import the type-annotation classes used below:

```python
from poethepoet.options.annotations import (
    ListType,
    Metadata,
    PrimitiveType,
    TypeAnnotation,
    UnionType,
)
```

`Annotated`, `Sequence`, `pytest`, `ConfigValidationError`, and `PoeOptions` are already imported at the top of the file from previous tasks — no new top-level imports beyond the line above.

Append:

```python
def test_annotated_nests_inside_union_branch_is_parsed():
    """Union-of-Annotated parses to a UnionType whose specific branch carries
    the inner Metadata."""

    parsed = TypeAnnotation.parse(
        str | Annotated[Sequence[str], Metadata(min_items=1)] | None
    )
    assert isinstance(parsed, UnionType)

    list_branch = next(
        vt for vt in parsed._value_types if isinstance(vt, ListType)
    )
    assert list_branch.metadata_get("min_items") == 1

    str_branch = next(
        vt for vt in parsed._value_types if isinstance(vt, PrimitiveType)
    )
    assert str_branch._metadata is None
```

- [ ] **Step 2: Write failing tests for propagation removal**

Continue appending to `tests/options/test_metadata_constraints.py`:

```python
def test_union_does_not_propagate_metadata_to_children():
    """Metadata attached at Annotated[Union[...], Metadata(...)] stays on the
    UnionType — it is NOT copied into child TypeAnnotations."""

    parsed = TypeAnnotation.parse(
        Annotated[str | int, Metadata(config_name="foo")]
    )
    assert isinstance(parsed, UnionType)
    assert parsed.metadata_get("config_name") == "foo"
    for branch in parsed._value_types:
        assert branch._metadata is None


def test_union_str_or_list_with_min_items_on_list_branch():
    """The motivating example: `min_items=1` lives on the list branch and
    rejects empty lists, but the string branch is unaffected."""

    class StrOrListOpt(PoeOptions):
        value: (
            str | Annotated[Sequence[str], Metadata(min_items=1)] | None
        ) = None

    # String branch — any string OK (even empty).
    options = next(StrOrListOpt.parse({"value": ""}))
    assert options.get("value") == ""

    # List branch with items — OK.
    options = next(StrOrListOpt.parse({"value": ["a"]}))
    assert options.get("value") == ["a"]

    # List branch empty — rejected.
    with pytest.raises(ConfigValidationError):
        list(StrOrListOpt.parse({"value": []}))
```

- [ ] **Step 3: Write failing tests for `min_items` / `max_items`**

```python
def test_min_items_rejects_short_list():
    class MinItemsOpt(PoeOptions):
        items: Annotated[Sequence[str], Metadata(min_items=2)] = ()

    next(MinItemsOpt.parse({"items": ["a", "b"]}))  # at boundary
    with pytest.raises(ConfigValidationError) as exc_info:
        list(MinItemsOpt.parse({"items": ["a"]}))
    assert "items" in str(exc_info.value)
    assert "2" in str(exc_info.value)


def test_max_items_rejects_long_list():
    class MaxItemsOpt(PoeOptions):
        items: Annotated[Sequence[str], Metadata(max_items=2)] = ()

    next(MaxItemsOpt.parse({"items": ["a", "b"]}))  # at boundary
    with pytest.raises(ConfigValidationError):
        list(MaxItemsOpt.parse({"items": ["a", "b", "c"]}))


def test_min_length_does_not_apply_to_lists():
    """After the rename, min_length is exclusively a string constraint.
    Attaching it to a list field has no effect at runtime (the schema
    generator in Phase 2 raises on this mismatch — see spec §4)."""

    class MinLengthOnListOpt(PoeOptions):
        items: Annotated[Sequence[str], Metadata(min_length=99)] = ()

    # Empty list passes; min_length is ignored on lists.
    options = next(MinLengthOnListOpt.parse({"items": []}))
    assert options.get("items") == []
```

- [ ] **Step 4: Write failing test for `type_constraints()` mapping**

```python
def test_metadata_type_constraints_table():
    """Schema generator needs to know which constraints apply to which types.
    Field-level metadata (config_name, examples) is NOT in this table."""

    constraints = Metadata.type_constraints()
    assert constraints["pattern"] == frozenset({"string"})
    assert constraints["min_length"] == frozenset({"string"})
    assert constraints["max_length"] == frozenset({"string"})
    assert constraints["minimum"] == frozenset({"integer", "number"})
    assert constraints["maximum"] == frozenset({"integer", "number"})
    assert constraints["min_items"] == frozenset({"array"})
    assert constraints["max_items"] == frozenset({"array"})
    assert "config_name" not in constraints
    assert "examples" not in constraints
```

- [ ] **Step 5: Run tests to confirm they fail**

Run: `pytest tests/options/test_metadata_constraints.py -v -k "annotated_nests or propagate or str_or_list or min_items or max_items or min_length_does_not_apply or type_constraints"`

Expected: FAIL on at least the `min_items`/`max_items`/`type_constraints` tests (those fields/methods don't exist yet), and on `propagate` (children currently inherit metadata).

- [ ] **Step 6: Stop `UnionType` from propagating metadata**

In `poethepoet/options/annotations.py`, replace `UnionType.__init__` (currently lines 367–375) with:

```python
def __init__(self, annotation: Any, metadata: Any = None):
    super().__init__(annotation, metadata)
    self._value_types = tuple(
        TypeAnnotation.parse(arg) for arg in get_args(annotation)
    )
```

Delete the `_wrap_with_metadata` staticmethod entirely (currently lines 377–382). The metadata stays on the `UnionType` itself (via `super().__init__`); child branches are parsed unmodified.

Also delete the now-obsolete propagation comment immediately above the `tuple(...)` block.

- [ ] **Step 7: Add `min_items`, `max_items`, and `type_constraints()` to `Metadata`**

In `poethepoet/options/annotations.py`, replace the `Metadata` class (currently lines 59–87) with:

```python
class Metadata:
    __slots__ = (
        "config_name",
        "examples",
        "max_items",
        "max_length",
        "maximum",
        "min_items",
        "min_length",
        "minimum",
        "pattern",
    )

    def __init__(
        self,
        *,
        config_name: str | None = None,
        pattern: str | None = None,
        examples: list[Any] | None = None,
        minimum: float | None = None,
        maximum: float | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        min_items: int | None = None,
        max_items: int | None = None,
    ):
        self.config_name = config_name
        self.pattern = pattern
        self.examples = examples
        self.minimum = minimum
        self.maximum = maximum
        self.min_length = min_length
        self.max_length = max_length
        self.min_items = min_items
        self.max_items = max_items

    @classmethod
    def type_constraints(cls) -> dict[str, frozenset[str]]:
        # Constructed on demand: only schema generation reads this, and that
        # runs offline. Keeping it out of the class body avoids paying the
        # construction cost on every CLI invocation. Field-level fields
        # (config_name, examples) are not listed — they apply to any field
        # regardless of value type.
        return {
            "pattern":    frozenset({"string"}),
            "minimum":    frozenset({"integer", "number"}),
            "maximum":    frozenset({"integer", "number"}),
            "min_length": frozenset({"string"}),
            "max_length": frozenset({"string"}),
            "min_items":  frozenset({"array"}),
            "max_items":  frozenset({"array"}),
        }
```

No new top-level imports are needed.

- [ ] **Step 8: Migrate `ListType.validate` from `min_length`/`max_length` to `min_items`/`max_items`**

In `poethepoet/options/annotations.py`, replace `ListType.validate` (currently lines 313–337) with:

```python
def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
    if not isinstance(value, list | tuple):
        yield f"Option {self._format_path(path)!r} must be a list"
        return

    if (min_items := self.metadata_get("min_items")) is not None and len(
        value
    ) < min_items:
        yield (
            f"Option {self._format_path(path)!r} requires at least "
            f"{min_items} item(s), got {len(value)}"
        )
    if (max_items := self.metadata_get("max_items")) is not None and len(
        value
    ) > max_items:
        yield (
            f"Option {self._format_path(path)!r} allows at most "
            f"{max_items} item(s), got {len(value)}"
        )

    if isinstance(self._value_type, AnyType):
        return

    for idx, item in enumerate(value):
        yield from self._value_type.validate((*path, idx), item)
```

Only the keys read from `metadata_get` and the error-message text change. `min_length`/`max_length` continue to be read by `PrimitiveType.validate` for string fields and are unchanged there.

- [ ] **Step 9: Migrate `task/shell.py` to union-of-Annotated**

In `poethepoet/task/shell.py`, find the `TaskOptions` class (currently around lines 31–35):

```python
class TaskOptions(PoeTask.TaskOptions):
    interpreter: Annotated[
        ShellInterpreter | Sequence[ShellInterpreter] | None,
        Metadata(min_length=1),
    ] = None
    ignore_fail: bool | list[int] = False
```

Replace it with:

```python
class TaskOptions(PoeTask.TaskOptions):
    interpreter: (
        ShellInterpreter
        | Annotated[Sequence[ShellInterpreter], Metadata(min_items=1)]
        | None
    ) = None
    ignore_fail: bool | list[int] = False
```

The constraint now lives on the branch it applies to, with the name (`min_items`) that names what it actually constrains.

- [ ] **Step 10: Run tests**

Run: `pytest tests/options/test_metadata_constraints.py -v`

Expected: PASS — including `test_empty_interpreter_list_rejected` from Task 7 (which previously passed via propagation and now passes via direct attachment to the list branch).

Run: `poe test`

Expected: PASS — no regression.

Run: `poe types`

Expected: PASS.

Run: `poe lint`

Expected: PASS.

- [ ] **Step 11: Verify no other production callsite carries type-level metadata on a union**

Run:

```bash
grep -nE "Annotated\[[^]]*\|[^]]*,\s*Metadata\(" poethepoet/ -r --include='*.py'
```

For each match, inspect: the `Metadata(...)` kwargs must contain only field-level keys (`config_name`, `examples`). Any type-level key on a union is a bug — surface it.

Expected: only `executor/uv.py:35,41` and `task/expr.py:35` remain, all using `config_name` only.

- [ ] **Step 12: Commit**

```bash
git add poethepoet/options/annotations.py poethepoet/task/shell.py tests/options/test_metadata_constraints.py
git commit -m "$(cat <<'EOF'
refactor: scope Metadata to specific branches; add min_items/max_items

Metadata splits into field-level (config_name, examples) and type-level
(pattern, minimum, maximum, min_length, max_length, min_items, max_items)
fields. UnionType no longer propagates outer Metadata into child branches:
type-level constraints must be attached to the specific branch via
Annotated[T, Metadata(...)] inside the union. Adds min_items/max_items
for arrays — mirroring JSON Schema's separate vocabulary — and migrates
ShellTask.interpreter to the union-of-Annotated form.
Metadata.type_constraints() is the single source of truth the Phase 2
schema generator will use to validate that constraints are attached to
compatible types. It's a lazy classmethod so the construction cost is
deferred out of the CLI startup path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

- [ ] **Step 1: Run the full quality suite**

Run: `poe check`
Expected: PASS — `docs-check`, `style`, `types`, `lint`, `test` all green.

- [ ] **Step 2: Confirm no regression in existing fixture configs**

Run: `pytest tests/ -v` and skim the output for any unexpected failures or warnings related to PoeOptions parsing.

Expected: PASS.

- [ ] **Step 3: Confirm the docstring helper is callable from a REPL-style check**

Run:

```bash
python -c "
from poethepoet.task.cmd import CmdTask
print(CmdTask.TaskOptions.description_for_field('cwd'))
print(CmdTask.TaskOptions.description_for_field('use_exec'))
print(CmdTask.TaskOptions.description_for_field('empty_glob'))
"
```

Expected: three non-`None` description strings printed.

- [ ] **Step 4: Verify the git log is clean and the commits tell a story**

Run: `git log --oneline development..HEAD`

Expected: roughly 11–12 commits, in this approximate order:
1. Introduce `ShellInterpreter` Literal alias + `register_type_alias` helper
2. Tighten `ShellTask` interpreter to Literal
3. Tighten `ProjectConfig` shell_interpreter to Literal
4. (optional) Any additional Literal tightening surfaced by the audit
5. Add `pattern` to Metadata
6. Add `examples` to Metadata
7. Add `minimum`/`maximum` to Metadata
8. Add `min_length`/`max_length` to Metadata (and restore empty-list rejection)
9. Add class-attribute docstring extraction
10. Backfill docstrings on PoeOptions classes
11. Document docstring convention in CLAUDE.md
12. Scope Metadata to specific branches; add `min_items`/`max_items`

Each commit should be reviewable on its own. If any commit bundles unrelated changes, consider rebasing to split before opening a PR.

Phase 1 is complete.

---

## What Phase 2 expects from this work

Phase 2 will assume:
- `PoeOptions.description_for_field(name)` returns docstring text for every annotated field on every PoeOptions subclass (no `None` for fields that ship in production code — only for synthetic test classes).
- `Metadata` exposes `pattern`, `examples`, `minimum`, `maximum`, `min_length`, `max_length`, `min_items`, `max_items` as documented attributes, each `None` when unset.
- `Metadata.type_constraints()` returns the source-of-truth mapping from type-level constraint name to applicable JSON Schema type kinds. The schema generator consumes this directly to validate that constraints are attached to compatible types and raises a clear error on mismatch. It's a classmethod (lazy) rather than a class attribute, since the mapping is only needed during offline schema generation.
- `UnionType` does not propagate metadata into its child branches — type-level constraints live on the specific branch via `Annotated[T, Metadata(...)]`. The schema generator can treat each branch's metadata as authoritative for that branch.
- `ShellInterpreter` is importable from `poethepoet.config` (alongside `KNOWN_SHELL_INTERPRETERS`).
- `PrimitiveType.validate` and `ListType.validate` enforce Metadata constraints, with messages that name the field, the constraint, and the offending value.

If any of these assumptions fail to hold at the start of Phase 2, treat them as bugs in Phase 1's output and fix before continuing.
