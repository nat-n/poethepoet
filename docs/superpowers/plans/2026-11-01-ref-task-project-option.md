# `ref` Task `project` Option Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a `ref` task run a task from another poe project (`project = "packages/${name}"`) in-process, with that project's own config, env and executor, as a drop-in replacement for `cmd = "poe -C <project> <task>"`.

**Architecture:** A cross-project ref loads the target project once per run (a cached `LoadedProject`: `PoeConfig` + lazily-validating `TaskSpecFactory`), derives a fresh child `RunContext` per call that shares the root's UI, dry-run flag and shutdown handling, builds the child env on top of the ref task's env, and runs the target (and its graph) there. Setup failures surface as stacked `ExecutionError`s. Pass 1 duplicates the `PoeThePoet` logic it needs into one module; pass 2 consolidates after an operator checkpoint.

**Tech Stack:** Python (asyncio), pytest via `poe test`, ruff, mypy, Sphinx docs, the bundled Agent Skill.

**Spec:** `docs/superpowers/specs/2026-11-01-ref-task-project-option-design.md`

## Global Constraints

- Branch from `development`; never commit to `main`. Don't commit `CLAUDE.md` or `docs/agents/` (unrelated working-tree changes).
- Relative imports inside `poethepoet`; type-only imports in `TYPE_CHECKING` blocks; lazy runtime imports for anything not needed at CLI startup.
- No single-character variable names; use the walrus operator where applicable.
- Docstrings are at least three lines: `"""` alone, content, `"""` alone.
- Every `PoeOptions` field has a class-attribute docstring.
- Only `PoeException`/`ExecutionError` may escape; no bare `KeyError` etc.
- Existing error output must be unchanged: single-level `From:` lines, the `From: {__cause__!r}` repr lines, and argparse usage output for in-project refs and CLI calls.
- Root config env must never override the child project's config env.
- No added cost for poe runs that don't use a cross-project ref (no eager loading, lazy imports).
- Don't bump `poethepoet/skills/poethepoet/version.txt`.
- User docs stay brief (no obscure edge cases).
- `poe lint`, `poe types` pass; run `poe format` before each commit.

## Review Focus

- `project` given as an absolute path (e.g. `${POE_ROOT}/packages/foo`) — should work like a relative one. Test: Task 4.
- `project` pointing at a dir whose config is `poe_tasks.toml`, not `pyproject.toml` — should load. Test: Task 4.
- `project = "."` (the calling project itself) — should run the root's own task in a fresh child context. Test: Task 4.
- `project` templating with an unset var (`packages/${NOPE}`) — should give the stacked "No poe configuration found" error, not a crash. Test: Task 5.
- The same project first referenced concurrently from two `parallel` branches — should load once. Test: Task 6.

---

### Task 1: Fix `uses`/`uses_env` sourced from an in-project ref

Fixes the existing bug (spec §4.5.1): `uses = { X = "r" }` with `r = { ref = "_hi" }` crashes with `KeyError: ('r',)`.

**Files:**
- Modify: `poethepoet/context.py` (`RunContext`, `TaskOutputCache`)
- Modify: `poethepoet/task/ref.py` (`RefTask._handle_run`)
- Modify: `tests/fixtures/refs_project/pyproject.toml`
- Test: `tests/test_ref_task.py`, `tests/test_task_output_cache.py` (new)

**Interfaces:**
- Produces: `RunContext.adopt_task_output(self, invocation: tuple[str, ...], source_context: RunContext, source_invocation: tuple[str, ...]) -> None`. It copies the raw captured output stored under `source_invocation` in `source_context` to `invocation` in `self`, and does nothing if the source has none.
- Produces: `TaskOutputCache.get_task_output` raises `ExecutionError(f"No captured output available for task {invocation[0]!r}")` when the invocation is missing.

- [ ] **Step 0: Create the feature branch**

```bash
git fetch origin && git switch -c feat/ref-project-option origin/development
```

The untracked spec and plan files come with you. Leave `CLAUDE.md` and `docs/agents/` unstaged.

- [ ] **Step 1: Add fixture tasks to `tests/fixtures/refs_project/pyproject.toml`**

```toml
[tool.poe.tasks._say-hi]
cmd = "poe_test_echo hi"

[tool.poe.tasks.say-hi-ref]
ref = "_say-hi"

[tool.poe.tasks.say-hi-ref-ref]
ref = "say-hi-ref"

[tool.poe.tasks.use-ref-output]
cmd  = "poe_test_echo got ${OUT}"
uses = { OUT = "say-hi-ref" }

[tool.poe.tasks.use-ref-ref-output]
cmd  = "poe_test_echo got ${OUT}"
uses = { OUT = "say-hi-ref-ref" }

[tool.poe.tasks._emit-greeting]
cmd = "poe_test_echo GREETING=hello"

[tool.poe.tasks.emit-greeting-ref]
ref = "_emit-greeting"

[tool.poe.tasks.use-ref-env]
cmd      = "poe_test_echo ${GREETING}"
uses_env = ["emit-greeting-ref"]
```

- [ ] **Step 2: Write the failing tests**

In `tests/test_ref_task.py`:

```python
@pytest.mark.parametrize("task", ["use-ref-output", "use-ref-ref-output"])
def test_uses_output_of_ref_task(run_poe, task):
    result = run_poe(task, project="refs")
    assert result.code == 0
    assert result.stdout == "got hi\n"


def test_uses_env_from_ref_task(run_poe):
    result = run_poe("use-ref-env", project="refs")
    assert result.code == 0
    assert result.stdout == "hello\n"
```

In `tests/test_task_output_cache.py`:

```python
import pytest

from poethepoet.context import TaskOutputCache
from poethepoet.exceptions import ExecutionError


def test_missing_task_output_raises_execution_error():
    with pytest.raises(ExecutionError, match="No captured output available for task 'x'"):
        TaskOutputCache().get_task_output(("x",))
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `poe test tests/test_ref_task.py -k "uses_output_of_ref or uses_env_from_ref" tests/test_task_output_cache.py`
Expected: FAIL. The ref tests fail with `KeyError: ('say-hi-ref',)` (or similar), and the cache test fails with `KeyError`.

- [ ] **Step 4: Implement**

- In `TaskOutputCache.get_task_output`, raise the `ExecutionError` above when the invocation is missing.
- Add `adopt_task_output` to `RunContext`. Copy the stored string directly; don't round-trip through `save_task_output`, which decodes bytes.
- In `RefTask._handle_run`, add the copy-up after the target has finished, on both the plain path and the `_run_task_graph` path. When `self.capture_stdout is True` (exactly `True`, not a file path), call `context.adopt_task_output(self.invocation, context, task.invocation)`. Chains of refs work recursively, because each ref copies from its own direct target.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `poe test tests/test_ref_task.py tests/test_task_output_cache.py tests/test_graph_execution.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
poe format && git add poethepoet/context.py poethepoet/task/ref.py tests/fixtures/refs_project/pyproject.toml tests/test_ref_task.py tests/test_task_output_cache.py
git commit -m "fix: support uses and uses_env sourced from a ref task"
```

---

### Task 2: Multi-level `ExecutionError` causes

Implements spec §5.1.

**Files:**
- Modify: `poethepoet/exceptions.py` (`ExecutionError`)
- Modify: `poethepoet/ui.py` (`PoeUi.print_error`)
- Test: `tests/test_error_output.py` (new)

**Interfaces:**
- Produces: `ExecutionError.causes: tuple[str, ...]`, built from the explicit `args[0]` cause only:
  - an `ExecutionError` cause contributes `(cause.msg, *cause.causes)`
  - a `PoeException` cause contributes `(cause.msg,)`, plus `(cause.cause,)` if it has one
  - any other exception contributes `(cause.args[0],)`
- Produces: `ExecutionError.cause` stays available as `causes[0]`, or `None` when there are no causes, so existing readers are unaffected.
- `print_error` prints one `From:` line per entry in `causes`. The `__cause__` repr line logic stays as it is.

- [ ] **Step 1: Write the failing tests in `tests/test_error_output.py`**

```python
from io import StringIO

from poethepoet.exceptions import ExecutionError, PoeException
from poethepoet.io import PoeIO
from poethepoet.ui import PoeUi


def render_error(error):
    output = StringIO()
    PoeUi(io=PoeIO(output=output, error=output, make_default=False)).print_error(error)
    return output.getvalue()


def test_single_level_cause_unchanged():
    assert render_error(ExecutionError("Outer", ValueError("inner"))) == (
        "Error: Outer\n     | From: inner\n"
    )


def test_multi_level_causes_render_one_line_each():
    error = ExecutionError("Outer", ExecutionError("Middle", ExecutionError("Innermost")))
    assert render_error(error) == (
        "Error: Outer\n     | From: Middle\n     | From: Innermost\n"
    )


def test_poe_exception_cause_in_chain():
    assert render_error(ExecutionError("Outer", PoeException("Config broke"))) == (
        "Error: Outer\n     | From: Config broke\n"
    )
```

- [ ] **Step 2: Run them to verify they fail**

Run: `poe test tests/test_error_output.py`
Expected: `test_multi_level_causes_render_one_line_each` FAILS because the `Innermost` line is missing. The other two pass already, pinning the current behaviour.

- [ ] **Step 3: Implement `causes` and update `print_error`**

- [ ] **Step 4: Run the full suite (checkpoint)**

Run: `poe test`
Expected: PASS. **If any existing test now fails because a nested error gains extra `From:` lines, stop and report the affected tests to the operator before changing them.** The spec requires existing output to be unchanged.

- [ ] **Step 5: Commit**

```bash
poe format && git add poethepoet/exceptions.py poethepoet/ui.py tests/test_error_output.py
git commit -m "feat: report the full chain of explicit error causes"
```

---

### Task 3: `project` option shape, load-time validation and schema

Implements spec §3 and §7.

**Files:**
- Modify: `poethepoet/task/ref.py` (`RefTask.TaskOptions`, `TaskSpec._task_validations`, `TaskSpec.accepts_option`, `__schema_fragment__`)
- Create: `tests/schema/fixtures/invalid/ref_project_and_cwd.toml`
- Regenerate: `docs/_static/partial-poe.json` (via `poe schema-build`)
- Test: `tests/test_ref_task_project.py` (new)

**Interfaces:**
- Produces: `RefTask.TaskOptions.project: Annotated[str, Metadata(pattern=r"\S")] | None = None`, with the docstring from spec §3 verbatim.
- Error copy, verbatim: `"'project' and 'cwd' options cannot be both provided on the same task."`

- [ ] **Step 1: Write the failing tests in `tests/test_ref_task_project.py`**

```python
def test_ref_project_rejects_cwd(run_poe, temp_pyproject):
    project_path = temp_pyproject("""
        [tool.poe.tasks.bad]
        ref = "x"
        project = "sub"
        cwd = "sub"
        """)
    result = run_poe("bad", cwd=project_path)
    assert result.code == 1
    assert (
        "'project' and 'cwd' options cannot be both provided on the same task."
        in result.capture
    )


def test_ref_project_target_not_checked_at_load(run_poe, temp_pyproject):
    project_path = temp_pyproject("""
        [tool.poe.tasks.other]
        cmd = "poe_test_echo ok"

        [tool.poe.tasks.ghost]
        ref = "nope"
        project = "missing"

        [tool.poe.tasks.ghost-capture]
        ref = "nope"
        project = "missing"
        capture_stdout = "out.txt"
        """)
    result = run_poe("other", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "ok\n"
```

Match how the existing `temp_pyproject` tests in `tests/test_ref_task.py` (around line 264) dedent their TOML.

- [ ] **Step 2: Add the schema fixture `tests/schema/fixtures/invalid/ref_project_and_cwd.toml`**

```toml
# expected_error: 'project' and 'cwd' options cannot be both provided
[tool.poe.tasks.bad]
ref = "x"
project = "sub"
cwd = "sub"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `poe test tests/test_ref_task_project.py && poe test-schema`
Expected: FAIL, with `project` reported as an unrecognised option.

- [ ] **Step 4: Implement**

- Add the field.
- In `TaskOptions.validate()`, raise the error copy when both `project` and `cwd` are set.
- In `__schema_fragment__`, add `"if": {"required": ["project"]}` and `"then": {"properties": {"cwd": False}}`. Follow the `CmdTask.__schema_fragment__` precedent and its comment about ajv `strictRequired`.
- In `_task_validations`, skip the unknown-task, `use_exec` and `capture_stdout` checks when `project` is set.
- In `accepts_option`, return `True` for `capture_stdout` when `self.options.project` is set.

- [ ] **Step 5: Regenerate the schema and verify**

Run: `poe schema-build && poe schema-check-drift && poe test-schema && poe test tests/test_ref_task_project.py tests/test_ref_task.py`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
poe format && git add poethepoet/task/ref.py docs/_static/partial-poe.json tests/schema/fixtures/invalid/ref_project_and_cwd.toml tests/test_ref_task_project.py
git commit -m "feat: add project option to ref tasks (config and schema)"
```

---

### Task 4: Run the referenced task in its own project

Implements spec §4.1–§4.5 (happy path) and §9a pass 1.

**Files:**
- Create: `poethepoet/task/project_ref.py`. This is the single home for logic duplicated from `PoeThePoet`.
- Modify: `poethepoet/context.py` (`RunContext.__init__`, new `for_project`, `get_loaded_project`)
- Modify: `poethepoet/task/base.py` (`TaskSpecFactory`)
- Modify: `poethepoet/config/config.py` (factor out `find_config_file` from `load`)
- Modify: `poethepoet/task/ref.py` (`_handle_run` branches on `project`)
- Create fixture: `tests/fixtures/project_refs_project/` (files below)
- Test: `tests/test_ref_task_project.py`

**Interfaces:**
- Consumes: `RunContext.adopt_task_output` (Task 1).
- Produces, in `poethepoet/task/project_ref.py`:
  - `def resolve_project_path(project_template: str, env: TaskEnv, config: PoeConfig) -> Path` resolves the path:
    - it templates with `env.fill_template(parse_template(...))`
    - a relative result is joined to `config.project_dir`, then `.resolve()`d
    - this matches `PoeTask.get_working_dir`
  - `@dataclass class LoadedProject` with fields `config: PoeConfig` and `specs: TaskSpecFactory`.
  - `async def load_project(config_file: Path, io: PoeIO) -> LoadedProject` builds `PoeConfig(cwd=config_file.parent, io=io)`, then awaits `load(target_path=config_file)`. It returns a factory built with `validate_on_get=True`.
  - `def build_target_context(project: LoadedProject, task_spec: PoeTask.TaskSpec, parent_ctx: TaskContext) -> TaskContext` sets:
    - `config` and `specs` from `project`
    - `cwd=str(task_spec.source.cwd)`
    - `io=PoeIO(parent=parent_ctx.io, baseline_verbosity=task_spec.options.get("verbosity", project.config.verbosity))`
    - `ui=parent_ctx.ui`
  - `async def run_target(task: PoeTask, context: RunContext, task_state: PoeTaskRun, *, ignore_fail: bool, start_error: Callable[[Exception], ExecutionError]) -> None` duplicates `RefTask`'s run/graph logic, including `ignore_fail` warnings, against the child context. Only exceptions raised while *starting* the target are passed through `start_error` and re-raised: building the `TaskExecutionGraph`, and the target's own `task.run(...)` call, whether as the graph sink or directly. Failures that come from waiting on runs are not wrapped. Task 5 supplies the real `start_error`; in this task, pass one that returns the error unchanged.
- Produces, in `poethepoet/context.py`:
  - `RunContext.__init__` gains keyword-only `shutdown_manager: ShutdownManager | None = None` and `loaded_projects: dict[Path, asyncio.Future[LoadedProject]] | None = None`. When given, it reuses them instead of creating new ones.
  - `def for_project(self, config: PoeConfig, base_env: Mapping[str, str]) -> RunContext` returns a child that:
    - shares `ui`, `dry`, `poe_active`, `multistage`, the loop, the shutdown manager and `loaded_projects`
    - copies `enable_output_streaming` at creation
    - gets a fresh `exec_cache` and `TaskOutputCache`, and an env built by `__init__` from `config` and `base_env`
    - never installs a signal handler itself
  - `async def get_loaded_project(self, project_path: Path, io: PoeIO) -> LoadedProject` works in three steps:
    1. It resolves the config file with `PoeConfig.find_config_file(project_path)` and uses that path as the cache key (spec §4.2).
    2. It stores an `asyncio.Future` per key before awaiting, so concurrent callers share one load. If the load fails, the future holds the exception, so later callers get the same error.
    3. It calls `project_ref.load_project(config_file, io)` through the module attribute (`from .task import project_ref`, then `project_ref.load_project(...)`) so tests can monkeypatch it.
- Produces, in `poethepoet/config/config.py`:
  - `def find_config_file(self, target_path: Path) -> Path`. It is the discovery loop factored out of `PoeConfig.load`: it iterates `PoeConfigFile.find_config_files(target_path, filenames=self._config_filenames, search_parent=False)` and returns the resolved path of the first valid file. With no match, it raises the same `PoeException("No poe configuration found from location …")`, and a file that fails to parse raises the same error it does today. `load()` must use this helper too, so the two can't drift. Make it a classmethod or staticmethod if it doesn't need instance state, since `get_loaded_project` calls it before any `PoeConfig` exists for the child. This costs one config-file parse per distinct `project` spelling. Includes and `include_script`s only run in `load`, once per config file.
- Produces, in `poethepoet/task/base.py`:
  - `TaskSpecFactory.__init__(self, config: PoeConfig, validate_on_get: bool = False)`. When it's true, a named lookup (no `task_def`) validates the spec the first time, via `spec.validate(self.config, self)`. The name is added to a validated set *before* validating, so recursive lookups terminate.

- [ ] **Step 1: Create the fixture**

`tests/fixtures/project_refs_project/pyproject.toml`:

```toml
[tool.poe.env]
SHARED      = "from-root"
ROOT_ONLY   = "root"
OVERRIDABLE = "from-root"

[tool.poe.tasks._prep]
cmd = "poe_test_echo root-prep"

[tool.poe.tasks.show-env]
cmd = "poe_test_echo root show-env"

[tool.poe.tasks.foo-env]
ref     = "show-env"
project = "packages/foo"
env     = { REF_VAR = "from-ref" }

[tool.poe.tasks.foo-env-file]
ref     = "show-env"
project = "packages/foo/pyproject.toml"

[tool.poe.tasks.foo-env-abs]
ref     = "show-env"
project = "${POE_ROOT}/packages/foo"

[tool.poe.tasks.run-in]
args    = [{ name = "project_name", positional = true, required = true }]
project = "packages/${project_name}"
ref     = "echo-args"

[tool.poe.tasks.foo-paths]
ref     = "show-paths"
project = "packages/foo"

[tool.poe.tasks.foo-graph]
ref     = "graph"
project = "packages/foo"

[tool.poe.tasks.foo-twice]
sequence = ["foo-env", "foo-paths", "foo-env-file", "foo-env-abs"]

[tool.poe.tasks.bar-hello]
ref     = "hello"
project = "packages/bar"

[tool.poe.tasks.tasksfile-hello]
ref     = "hello"
project = "packages/tasksfile"

[tool.poe.tasks.self-show-env]
ref     = "show-env"
project = "."
```

`tests/fixtures/project_refs_project/packages/foo/pyproject.toml`:

```toml
[tool.poe.env]
SHARED      = "from-foo"
OVERRIDABLE = { default = "from-foo" }
FOO_ONLY    = "foo"

[tool.poe.tasks._prep]
cmd = "poe_test_echo foo-prep"

[tool.poe.tasks.show-env]
cmd = "poe_test_echo SHARED=${SHARED} OVERRIDABLE=${OVERRIDABLE} ROOT_ONLY=${ROOT_ONLY} FOO_ONLY=${FOO_ONLY} REF_VAR=${REF_VAR}"

[tool.poe.tasks.echo-args]
cmd = "poe_test_echo foo got"

[tool.poe.tasks.show-paths]
cmd = "poe_test_echo ${POE_ROOT} ${POE_CONF_DIR} ${POE_PWD}"

[tool.poe.tasks.graph]
cmd  = "poe_test_echo graph ${PREP}"
uses = { PREP = "_prep" }
```

`tests/fixtures/project_refs_project/packages/bar/pyproject.toml`:

```toml
[tool.poe]
executor = { type = "virtualenv", location = "missing_venv" }

[tool.poe.tasks.hello]
cmd = "poe_test_echo hello from bar"

[tool.poe.tasks.broken]
cmd = ""
```

`tests/fixtures/project_refs_project/packages/tasksfile/poe_tasks.toml`:

```toml
[tasks.hello]
cmd = "poe_test_echo hello from tasksfile"
```

- [ ] **Step 2: Write the failing tests (append to `tests/test_ref_task_project.py`)**

```python
import pytest


@pytest.fixture
def root_dir(projects):
    return projects["project_refs"]


@pytest.fixture
def project_load_calls(monkeypatch):
    from poethepoet.task import project_ref

    calls = []
    original = project_ref.load_project

    async def counting_load(config_file, io):
        calls.append(config_file)
        return await original(config_file, io)

    monkeypatch.setattr(project_ref, "load_project", counting_load)
    return calls


def test_ref_project_env_layering(run_poe):
    result = run_poe("foo-env", project="project_refs")
    assert result.code == 0
    assert result.stdout == (
        "SHARED=from-foo OVERRIDABLE=from-root ROOT_ONLY=root FOO_ONLY=foo "
        "REF_VAR=from-ref\n"
    )


@pytest.mark.parametrize("task", ["foo-env-file", "foo-env-abs"])
def test_ref_project_file_and_absolute_paths(run_poe, task):
    result = run_poe(task, project="project_refs")
    assert result.code == 0
    assert result.stdout == (
        "SHARED=from-foo OVERRIDABLE=from-root ROOT_ONLY=root FOO_ONLY=foo REF_VAR=\n"
    )


def test_ref_project_templated_path_and_extra_args(run_poe):
    result = run_poe("run-in", "foo", "--", "--strict", project="project_refs")
    assert result.code == 0
    assert result.stdout == "foo got --strict\n"


def test_ref_project_paths_are_childs(run_poe, root_dir):
    foo_dir = root_dir / "packages" / "foo"
    result = run_poe("foo-paths", project="project_refs")
    assert result.stdout == f"{foo_dir} {foo_dir} {root_dir}\n"


def test_ref_project_target_uses_resolve_in_child(run_poe):
    result = run_poe("foo-graph", project="project_refs")
    assert result.code == 0
    assert result.stdout == "graph foo-prep\n"


def test_ref_project_uses_child_executor(run_poe, root_dir):
    result = run_poe("bar-hello", project="project_refs")
    assert result.code == 1
    assert (
        "Could not find valid virtualenv at configured location: "
        f"{root_dir / 'packages' / 'bar' / 'missing_venv'}"
    ) in result.capture


def test_ref_project_cli_executor_override_and_lazy_validation(run_poe):
    # bar's invalid 'broken' task must not block running 'hello'
    result = run_poe("-e", "simple", "bar-hello", project="project_refs")
    assert result.code == 0
    assert result.stdout == "hello from bar\n"


def test_ref_project_poe_tasks_file(run_poe):
    result = run_poe("tasksfile-hello", project="project_refs")
    assert result.stdout == "hello from tasksfile\n"


def test_ref_project_self_reference(run_poe):
    result = run_poe("self-show-env", project="project_refs")
    assert result.stdout == "root show-env\n"


def test_ref_project_loaded_once_per_run(run_poe, project_load_calls):
    # dir, config-file and absolute spellings of the same project share one load
    result = run_poe("foo-twice", project="project_refs")
    assert result.code == 0
    assert len(project_load_calls) == 1
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `poe test tests/test_ref_task_project.py`
Expected: the new tests FAIL. Without the runtime branch, the ref looks up `show-env` in the root project.

- [ ] **Step 4: Implement `TaskSpecFactory(validate_on_get=...)`**

- [ ] **Step 5: Implement `RunContext` changes (`__init__` kwargs, `for_project`, `get_loaded_project`)**

- [ ] **Step 6: Implement `poethepoet/task/project_ref.py`**

- [ ] **Step 7: Wire `RefTask._handle_run`**

When `self.spec.options.project` is set, after the existing arg parsing and `ref_invocation` computation:

1. `path = resolve_project_path(...)`
2. `project = await context.get_loaded_project(path, self.ctx.io)`
3. `child = context.for_project(project.config, env.get_subprocess_env_vars())`
4. Look up the spec, then `create_task(invocation=ref_invocation, ctx=build_target_context(...), capture_stdout=self.capture_stdout)`.
5. `await run_target(...)`.
6. If `self.capture_stdout is True`, call `context.adopt_task_output(self.invocation, child, task.invocation)`.

Put this in a private `_run_in_project` method, so `_handle_run` only branches. Leave the in-project path unchanged.

Before relying on lazy validation, check whether strict `PoeConfig.load` already validates individual task definitions. `test_ref_project_cli_executor_override_and_lazy_validation` will fail at load if it does; in that case, move those checks onto the lazy path (spec §4.2).

- [ ] **Step 8: Run the tests to verify they pass**

Run: `poe test tests/test_ref_task_project.py tests/test_ref_task.py tests/test_graph_execution.py tests/test_includes.py`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
poe format && poe lint && poe types
git add poethepoet/task/project_ref.py poethepoet/context.py poethepoet/config/config.py poethepoet/task/base.py poethepoet/task/ref.py tests/fixtures/project_refs_project tests/test_ref_task_project.py
git commit -m "feat: run ref task targets in another project"
```

---

### Task 5: Errors from cross-project refs

Implements spec §5 and §5.2.

**Files:**
- Modify: `poethepoet/task/ref.py` (`_run_in_project` wraps setup errors)
- Modify: `poethepoet/task/base.py` (`TaskContext`, `PoeTask.get_parsed_arguments`)
- Modify: `poethepoet/task/args.py` (`PoeTaskArgs.parse`)
- Modify: `poethepoet/task/project_ref.py` (`build_target_context` sets the quiet flag)
- Modify fixture: `tests/fixtures/project_refs_project/` (additions below)
- Test: `tests/test_ref_task_project.py`

**Interfaces:**
- Consumes: `ExecutionError.causes` (Task 2), and `run_target(..., start_error=...)` and `build_target_context` (Task 4).
- Produces: `TaskContext` gains a last field `quiet_arg_usage: bool = False`. `TaskContext.from_task` does not propagate it, so it applies only to a cross-project ref's direct target. `build_target_context` sets it to `True`.
- Produces: `PoeTaskArgs.parse(self, args, env, program_name, *, quiet_usage: bool = False)`. When `quiet_usage` is true:
  - argparse's stderr goes to a buffer and is not printed
  - argparse's message is the text after `": error: "` on the buffer's last non-empty line
  - it raises `ExecutionError(f"Invalid arguments for task {name!r}", ExecutionError(message)) from error`

  When `quiet_usage` is false, behaviour is unchanged.
- Headline copy, verbatim: `f"Task {self.name!r} could not run {target_name!r} in project {project_display}"`. Here `project_display` is the templated `project` value as written, e.g. `packages/foo`, not the resolved absolute path.
- Wrapped, with the original error as the explicit cause arg (not `raise … from`):
  - `PoeException`/`ExecutionError` from `get_loaded_project`
  - the unknown-task check: `ExecutionError(f"Unrecognized task {target_name!r}")`, raised when the name is not in `project.config.get_tasks()`
  - the spec lookup, including lazy validation
  - the run-time `use_exec` and `capture_stdout` target checks, with wording copied from `_task_validations`
  - `run_target`'s `start_error` hook

- [ ] **Step 1: Extend the fixture**

Add to the root `pyproject.toml`:

```toml
[tool.poe.tasks.missing-project]
ref     = "show-env"
project = "packages/nope"

[tool.poe.tasks.unset-var-project]
ref     = "show-env"
project = "packages/${NOPE}"

[tool.poe.tasks.foo-typo]
ref     = "chekc"
project = "packages/foo"

[tool.poe.tasks.bar-broken]
ref     = "broken"
project = "packages/bar"

[tool.poe.tasks.foo-bad-args]
ref     = "strict-args --bogus"
project = "packages/foo"

[tool.poe.tasks.foo-exec]
ref     = "exec-task"
project = "packages/foo"

[tool.poe.tasks.badconf-task]
ref     = "anything"
project = "packages/badconf"
```

Add to `packages/foo/pyproject.toml`:

```toml
[tool.poe.tasks.strict-args]
cmd  = "poe_test_echo mode=${mode}"
args = ["mode"]

[tool.poe.tasks.exec-task]
cmd      = "poe_test_echo exec"
use_exec = true
```

Create `packages/badconf/pyproject.toml`:

```toml
[tool.poe]
oops_invalid = "bad"

[tool.poe.tasks.anything]
cmd = "poe_test_echo anything"
```

- [ ] **Step 2: Write the failing tests**

```python
@pytest.mark.parametrize(
    ("task", "target", "project_display", "cause_lines"),
    [
        ("missing-project", "show-env", "packages/nope", ["No poe configuration found from location"]),
        ("unset-var-project", "show-env", "packages/", ["No poe configuration found from location"]),
        ("foo-typo", "chekc", "packages/foo", ["Unrecognized task 'chekc'"]),
        ("bar-broken", "broken", "packages/bar", ["Task has no content"]),
        ("foo-exec", "exec-task", "packages/foo", ["Illegal reference to task with 'use_exec' set to true: 'exec-task'"]),
        ("badconf-task", "anything", "packages/badconf", ["Unrecognized option 'oops_invalid'"]),
        ("foo-bad-args", "strict-args", "packages/foo", ["Invalid arguments for task 'strict-args'", "unrecognized arguments: --bogus"]),
    ],
)
def test_ref_project_errors_are_stacked(run_poe, task, target, project_display, cause_lines):
    result = run_poe(task, project="project_refs")
    assert result.code == 1
    assert (
        f"Error: Task {task!r} could not run {target!r} in project {project_display}\n"
        in result.capture
    )
    for line in cause_lines:
        assert f"     | From: {line}" in result.capture
    assert "Usage:" not in result.capture  # no help dump
    assert "usage:" not in result.capture  # no argparse usage for the child
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `poe test tests/test_ref_task_project.py -k errors_are_stacked`
Expected: FAIL, because the headline is missing and/or the help dump appears.

- [ ] **Step 4: Implement the quiet arg parsing (`TaskContext` field, `get_parsed_arguments` passing `quiet_usage=self.ctx.quiet_arg_usage`, `PoeTaskArgs.parse`)**

- [ ] **Step 5: Implement the wrapping in `_run_in_project` and pass the real `start_error` to `run_target`**

- [ ] **Step 6: Run the tests to verify they pass, plus the arg-error regression suites**

Run: `poe test tests/test_ref_task_project.py tests/test_ref_task.py tests/test_cli.py tests/test_arg_choices.py`
Expected: PASS, including the existing tests that assert argparse usage output for in-project tasks.

- [ ] **Step 7: Commit**

```bash
poe format && git add poethepoet/task/ref.py poethepoet/task/base.py poethepoet/task/args.py poethepoet/task/project_ref.py tests/fixtures/project_refs_project tests/test_ref_task_project.py
git commit -m "feat: stacked errors for cross-project ref failures"
```

---

### Task 6: Composition (uses, capture, ignore_fail, dry-run, parallel, verbosity)

Implements the remaining tests in spec §9 and §6.

**Files:**
- Modify fixture: `tests/fixtures/project_refs_project/` (additions below, plus `.gitignore`)
- Modify: whichever of `poethepoet/context.py`, `poethepoet/task/project_ref.py` or `poethepoet/task/ref.py` the tests show needs fixing. Most of these should pass already.
- Test: `tests/test_ref_task_project.py`

**Interfaces:**
- Consumes: everything from Tasks 1–5. No new interfaces.

- [ ] **Step 1: Extend the fixture**

Add to the root `pyproject.toml`:

```toml
[tool.poe.tasks.foo-hello]
ref     = "hello"
project = "packages/foo"

[tool.poe.tasks.use-foo-output]
cmd  = "poe_test_echo got ${OUT}"
uses = { OUT = "foo-hello" }

[tool.poe.tasks.foo-emit-env]
ref     = "emit-env"
project = "packages/foo"

[tool.poe.tasks.use-foo-env]
cmd      = "poe_test_echo token=${FOO_TOKEN}"
uses_env = ["foo-emit-env"]

[tool.poe.tasks.foo-hello-file]
ref            = "hello"
project        = "packages/foo"
capture_stdout = "hello.txt"

[tool.poe.tasks.foo-fail-ok]
ref         = "fail"
project     = "packages/foo"
ignore_fail = true

[tool.poe.tasks.para]
parallel = ["foo-hello", "show-env"]

[tool.poe.tasks.para-same-project]
parallel = ["foo-hello", "foo-env"]

[tool.poe.tasks.quiet-hello]
ref     = "hello"
project = "packages/quiet"

[tool.poe.tasks.quiet-between]
sequence = ["show-env", "quiet-hello", "show-env"]

[tool.poe.tasks.hello-all-inline]
sequence = [
  { ref = "hello", project = "packages/foo" },
  { ref = "hello", project = "packages/tasksfile" },
]

[tool.poe.tasks.hello-in]
args    = [{ name = "package", positional = true, required = true }]
project = "packages/${package}"
ref     = "hello"

[tool.poe.tasks.hello-all-generic]
sequence = ["hello-in foo", "hello-in tasksfile"]
```

Add to `packages/foo/pyproject.toml`:

```toml
[tool.poe.tasks.hello]
cmd = "poe_test_echo hello from foo"

[tool.poe.tasks.emit-env]
cmd = "poe_test_echo FOO_TOKEN=abc123"

[tool.poe.tasks.fail]
cmd = "poe_test_fail 0 3"
```

Create `packages/quiet/pyproject.toml`:

```toml
[tool.poe]
verbosity = -1

[tool.poe.tasks.hello]
cmd = "poe_test_echo quiet hello"
```

Create `tests/fixtures/project_refs_project/.gitignore` containing `packages/foo/hello.txt`.

- [ ] **Step 2: Write the tests**

```python
def test_ref_project_as_uses_source(run_poe):
    result = run_poe("use-foo-output", project="project_refs")
    assert result.code == 0
    assert result.stdout == "got hello from foo\n"


def test_ref_project_as_uses_env_source(run_poe):
    result = run_poe("use-foo-env", project="project_refs")
    assert result.stdout == "token=abc123\n"


def test_ref_project_capture_stdout_file(run_poe, root_dir):
    output_file = root_dir / "packages" / "foo" / "hello.txt"
    output_file.unlink(missing_ok=True)
    try:
        result = run_poe("foo-hello-file", project="project_refs")
        assert result.code == 0
        assert output_file.read_text() == "hello from foo\n"
    finally:
        output_file.unlink(missing_ok=True)


def test_ref_project_ignore_fail(run_poe):
    assert run_poe("foo-fail-ok", project="project_refs").code == 0


def test_ref_project_dry_run(run_poe):
    result = run_poe("-d", "foo-env", project="project_refs")
    assert result.code == 0
    assert result.capture == (
        "Poe <= poe_test_echo SHARED=from-foo OVERRIDABLE=from-root "
        "ROOT_ONLY=root FOO_ONLY=foo REF_VAR=from-ref\n"
    )
    assert result.stdout == ""


def test_ref_project_inside_parallel_keeps_prefixes(run_poe):
    result = run_poe("para", project="project_refs")
    assert result.code == 0
    assert sorted(result.stdout.splitlines()) == [
        "foo-hello | hello from foo",
        "show-env | root show-env",
    ]


def test_ref_project_concurrent_first_load_once(run_poe, project_load_calls):
    result = run_poe("para-same-project", project="project_refs")
    assert result.code == 0
    assert len(project_load_calls) == 1


@pytest.mark.parametrize("task", ["hello-all-inline", "hello-all-generic"])
def test_ref_project_fan_out_shapes(run_poe, task):
    result = run_poe(task, project="project_refs")
    assert result.code == 0
    assert result.stdout == "hello from foo\nhello from tasksfile\n"


def test_ref_project_child_verbosity_is_scoped(run_poe):
    result = run_poe("quiet-between", project="project_refs")
    assert result.stdout == "root show-env\nquiet hello\nroot show-env\n"
    assert result.capture.count("Poe => poe_test_echo root show-env") == 2
    assert "Poe => poe_test_echo quiet hello" not in result.capture
```

Use the parallel prefix format that `tests/test_parallel_tasks.py` asserts for named ref items. If the prefix for a string item differs from `"<task> | "`, follow those tests.

- [ ] **Step 3: Run the tests**

Run: `poe test tests/test_ref_task_project.py`
Expected: as many as possible PASS. For each failure, fix the cause in the files named above. Each must PASS before you commit.

- [ ] **Step 4: Commit**

```bash
poe format && git add tests/fixtures/project_refs_project tests/test_ref_task_project.py poethepoet
git commit -m "test: cross-project ref composition with uses, capture, parallel and verbosity"
```

---

### Task 7: User docs and Agent Skill guidance

Implements spec §8, plus the operator's request that the skill actively steer agents to this feature.

**Files:**
- Modify: `docs/tasks/task_types/ref.rst`
- Modify: `docs/guides/include_guide.rst`
- Modify: `poethepoet/skills/poethepoet/references/task-types.md` (`## ref` and `## cmd` sections)
- Modify: `poethepoet/skills/poethepoet/references/creating-tasks.md` (`## Compose tasks; don't call poe recursively`, plus a new `## Monorepos` section)
- Modify: `poethepoet/skills/poethepoet/SKILL.md` (the `ref` row of the task types table)
- Modify: `tests/skills/evals.json`; create `tests/skills/fixtures/monorepo/` (fixture project)

**Interfaces:** none.

- [ ] **Step 1: `docs/tasks/task_types/ref.rst`**

Add a section "Referencing a task in another project" after "Passing arguments" containing:
- the two TOML examples from spec §1
- one sentence on the mental model: it runs with that project's own config, env and executor, like `poe -C`, but in the same process
- one sentence on env: the subproject's `env` takes precedence; declare a var as `{ default = "…" }` there to let callers override it

Also add `project` to the "Available task options" list, with a one-line description.

- [ ] **Step 2: `docs/guides/include_guide.rst`**

In the intro paragraph's monorepo context, add one sentence. It says that to run a subproject's task with that subproject's own config and venv, rather than pulling its definitions into this project, you use a ref task with `project` (`:doc:` link to `ref`).

- [ ] **Step 3: Skill: `task-types.md`**

- In `## ref`: add a "Tasks in another project (monorepos)" sub-block. It holds the `check-project` example from spec §1, and says it is the replacement for `cmd = "poe -C <dir> <task>"`. It also gives the env precedence note in one line.
- In `## cmd`: add one line after "Use when". It tells agents that to run a task from a subproject, they must not write `cmd = "poe -C sub check"`, and must use a `ref` with `project` instead (see `## ref`).

- [ ] **Step 4: Skill: `creating-tasks.md`**

- Under "Compose tasks; don't call poe recursively": add a second ❌/✅ pair. The ❌ side is `shell = "poe -C packages/foo check\npoe -C packages/bar check"`. The ✅ side is the inline form below.
- Add a short `## Monorepos` section after "Splitting config with includes". It distinguishes the two tools:
  - `include` (+ `cwd`) pulls a subproject's task *definitions* into this project, and they run with this project's venv and env
  - `ref` + `project` runs a subproject's task as that subproject would, using its own venv, env and config

  It then shows both composition shapes verbatim, each with a one-line "use when":

  ```toml
  # Inline refs: a one-off fan-out over a few known packages
  [tool.poe.tasks.check-all]
  sequence = [
    { ref = "check", project = "packages/api" },
    { ref = "check", project = "packages/web" },
  ]
  ```

  ```toml
  # A generic task, reused by plain string refs: many packages, or callable alone
  [tool.poe.tasks.check-project]
  args    = [{ name = "package", positional = true, required = true }]
  project = "packages/${package}"
  ref     = "check"
  help    = "Run a package's check task"

  [tool.poe.tasks.check-all]
  parallel = ["check-project api", "check-project web"]
  ```

  End with one line: extra args reach the package task after `--`, e.g. `poe check-project api -- --strict`.
- Keep the `## ref` sub-block in `task-types.md` (Step 3) to the generic form only, with a pointer to this section for the inline form. That way the two shapes aren't duplicated across files.

- [ ] **Step 5: Skill: `SKILL.md`**

Change the `ref` table row's "When to use" cell to `reference another task (also in another project)`.

- [ ] **Step 6: Add a skill eval**

- Create `tests/skills/fixtures/monorepo/`, mirroring an existing fixture's layout. It has a root `pyproject.toml` with a `[tool.poe]` table and no tasks, plus `packages/api/pyproject.toml` and `packages/web/pyproject.toml`, each with its own `check` task.
- Append eval `id: 11` with `fixture: "monorepo"`.
  - Prompt: "Add a task to the root project that runs the check task in every package under packages/."
  - Expectations:
    1. the response defines tasks using `ref` with a `project` option
    2. the response does not use `poe -C` (or `poe --directory`) inside a `cmd` or `shell` task
    3. the per-package refs are composed with `sequence` or `parallel`, either as inline `{ ref, project }` items or as string refs to a generic task with a project arg

- [ ] **Step 7: Verify**

Run: `poe docs-check && poe test tests/skills tests/test_ref_task_project.py`
Expected: PASS. Then run the new eval once:

Run: `poe eval-skill -e 11`
Expected: the with-skill run meets all three expectations. If it doesn't, tighten the skill wording, not the eval. Report the result to the operator. This step costs money (`claude -p`), so run it once only.

- [ ] **Step 8: Commit**

```bash
git add docs/tasks/task_types/ref.rst docs/guides/include_guide.rst poethepoet/skills tests/skills
git commit -m "docs: document ref project option and steer the skill to it"
```

---

### Task 8: Consolidation checkpoint (pass 2)

Implements spec §9a pass 2. This needs operator review before any code changes (CLAUDE.md: present architectural changes before making them).

**Files:**
- Read: `poethepoet/task/project_ref.py`, `poethepoet/task/ref.py`, `poethepoet/app.py`

- [ ] **Step 1: Write a short consolidation proposal in chat (no code changes)**

It should cover:
- which functions in `project_ref.py` now mirror `PoeThePoet` (`_call` loading, `resolve_task`, `_run_task`/`_run_task_graph`) and `RefTask._run_task_graph`
- how each of the four degrees of freedom in spec §9a shows up in the code
- a proposed shared API, its rough shape, and which call sites move

- [ ] **Step 2: Wait for the operator's decision**

Implement pass 2 as an approved follow-up, either in this PR or a separate one as the operator chooses, with the full existing test suite as the safety net.

---

### Task 9: Final verification

- [ ] **Step 1: Run all quality checks**

Run: `poe check`
Expected: style, types, lint and tests all PASS.

- [ ] **Step 2: Check schema drift and skill reference accuracy once more**

Run: `poe schema-check-drift`
Expected: no drift. Re-read the changed skill sections against the final behaviour (CLAUDE.md: skill docs must not drift from behaviour).
