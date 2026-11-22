# `ref` Task `project` Option — Design

**Status:** Drafted 2026-11-01, builder-checked, pending operator approval.
**Author:** Design produced collaboratively with Claude.

## 1. Intent

Monorepos built with poe end up with tasks that shell out to a second poe process to
run a task in a subproject:

```toml
[tool.poe.tasks.check-foo]
cmd = "poe -C ./subproj_foo/pyproject.toml check"

[tool.poe.tasks.check-all]
shell = """
poe -C ./subproj_foo/pyproject.toml check
poe -C ./subproj_bar/pyproject.toml check
"""
```

This is ugly, and it is subtly wrong: the inner `poe` runs through the *root*
project's executor, so it is whichever `poe` happens to be on the root venv's PATH
(possibly a different version), and the root's `VIRTUAL_ENV` and config env leak
into it. It also costs a second Python startup and hides the subproject task from
poe's own machinery (dry-run, output prefixing in `parallel`, error reporting,
signal handling).

The `project` option makes a `ref` task reference a task defined in another poe
project:

```toml
[tool.poe.tasks.check-foo]
ref = "check"
project = "subproj_foo"

[tool.poe.tasks.check-project]
args = [{ name = "project_name", positional = true, required = true }]
project = "packages/${project_name}"
ref = "check"
```

`poe check-project foo -- --strict` runs foo's `check` task with `--strict`.

**Mental model:** a `ref` with `project` is a drop-in replacement for
`cmd = "poe -C <project> <task>"`, run in-process. The referenced task runs with the
referenced project's config: its executor/venv, its `env`/`envfile`, its includes,
its task definitions and deps. The calling project's IO and UI are shared.

## 2. Goals, non-goals, anti-goals

### Goals

- New `project` option on `ref` tasks, accepting a path (directory or config file)
  that supports `${VAR}` templating against the ref task's env, including its args.
- Behaviour equivalent to `poe -C <project> <invocation>` run in a subprocess whose
  process env is the ref task's env, except: in-process (no second interpreter),
  same poe version, root's `VIRTUAL_ENV`/`POE_ACTIVE` do not leak, and output,
  dry-run, verbosity, `capture_stdout`, `ignore_fail` and shutdown all behave as
  for any other ref.
- Errors from the referenced project surface as a stacked error from the ref task,
  never as a help-text dump and never as an unhandled exception.

### Non-goals

- Validating the referenced task at config load time. Subproject configs are only
  loaded when the ref task runs. Eager loading would cost latency on every poe
  invocation (including `--help`), and templated paths cannot be resolved statically
  anyway.
- Ref cycle detection, in-project or cross-project (operator decision). In-project
  ref cycles are not detected today either.
- Documenting or exposing the referenced task in the calling project's help output.
  The referenced task is an internal detail of the ref task; only the ref task's own
  `help`/`args` are shown.
- Cross-project `deps`/`uses`/`uses_env`. Only `ref` gains `project`. A referenced
  task's own deps resolve within its own project, so no task graph ever spans
  projects.
- Changing how argument errors are displayed for refs *within* a project, or for
  tasks invoked directly from the CLI.

### Anti-goals (failure even if it "works")

- Root config env silently overriding the subproject's config env (breaks the
  subproject in ways that differ from running it directly).
- Usage/help output that names a command nobody ran (e.g. `poe -C packages/foo …`)
  or that suggests the referenced task is a task of the calling project.
- Noticeable startup cost for poe invocations that don't run a cross-project ref.
- A sprawling caching subsystem. It must stay small.

## 3. Option shape and validation

### Field

On `RefTask.TaskOptions`:

```python
project: Annotated[str, Metadata(pattern=r"\S")] | None = None
"""
Path to another poe project (a directory or a config file) in which to look up and
run the referenced task, with that project's own config, env and executor. Relative
to the project root unless absolute. Environment variables can be used in the
format ${VAR_NAME}.
"""
```

### Validation (load time, cheap, no subproject I/O)

- `project` and `cwd` together → `ConfigValidationError`. The referenced task runs in
  its own project's working directory, so a `cwd` on the ref is meaningless.
  Express in `RefTask.TaskOptions.validate()` and mirror in
  `RefTask.__schema_fragment__` (e.g. `"not": {"required": ["cwd", "project"]}` or
  `dependentSchemas`), and add an invalid fixture under
  `tests/schema/fixtures/invalid/` with an `# expected_error:` header so the parity
  test pins it.
- `executor` stays forbidden (already the case for all refs).
- When `project` is set, `RefTask.TaskSpec._task_validations` skips the
  "unknown task", `use_exec` and `capture_stdout` target checks — the target isn't
  loaded. Those checks move to run time (see §5).
- `RefTask.TaskSpec.accepts_option("capture_stdout")` returns `True` when `project`
  is set (the target is unknown at load time); the run-time check in §5 covers it.

## 4. Runtime model

### 4.1 Resolving the project path

At run time, after args are parsed and registered on the ref task's env (as today):

1. Template `project` with `env.fill_template(...)`, the same way ref content is
   templated.
2. Resolve exactly like the `cwd` option in `PoeTask.get_working_dir`: relative paths
   are joined to `self.ctx.config.project_dir` and resolved.
3. Pass the result to `PoeConfig.load(target_path=...)`, which already accepts a
   file or a directory and, with an explicit target, does not search parent dirs.

The resolved path to the loaded config file (`config_file.path`, resolved) is the
**project key** used for caching.

### 4.2 The loaded project (cached per poe invocation)

A small new type — working name `LoadedProject` — holds what is genuinely
per-project and env-independent:

- the target `PoeConfig` (constructed with `cwd=<resolved dir>` and the calling
  task's `PoeIO`; never a new default `PoeIO`, since `make_default=True` mutates
  global state)
- its `TaskSpecFactory`, with **lazy per-spec validation**: a child task spec is
  validated (`task_spec.validate(config, specs)`) the first time it is looked up,
  and memoized. Every child task is created via a spec lookup, so the target and
  everything its graph or sequence/ref chain actually reaches gets validated, while
  invalid tasks elsewhere in the child project never block the caller. This differs
  from `PoeThePoet._call`, which validates all specs up front.
  Global config errors (structure of the config file, global `env`/`executor`
  options) still fail at load, since they affect every task. The builder should
  verify that strict `PoeConfig.load` doesn't deep-validate individual task
  definitions; if it does, those checks must move to the lazy path too.

Cache: a dict keyed by project key, owned by the root `RunContext` and shared by
reference with every child context, living for one poe invocation. No eviction or
invalidation. Concurrent first loads of the same project (e.g. two branches of a
`parallel`) must not both load: cache an `asyncio` future/task per key, or guard
with a lock. Because the key is the resolved config file path, the cache can only
be consulted after the path has been resolved to a file; resolving
`directory → config file` is cheap and may be done before the lookup.

`PoeThePoet` is not reused or nested: it is a CLI driver (argv parsing, help,
`run_async`), and `run_async` cannot be called from inside the running loop.
Whether `PoeThePoet` itself is refactored to use `LoadedProject` is left to the
builder; not required.

### 4.3 The child `RunContext` (fresh per ref invocation)

Today there is exactly one `RunContext` per poe invocation (`PoeThePoet.run_context`
→ `RunContext.scope`), reused via `existing=`. This design adds a way to derive a
child context for another project — working name `RunContext.for_project(...)`.

| Child context field | Source |
|---|---|
| `config` | the target `PoeConfig` |
| `env` | built per §4.4 |
| `_task_outputs` | **fresh** `TaskOutputCache` — `uses` output is scoped to this ref invocation's graph, as it would be in a `poe -C` subprocess |
| `exec_cache` | **fresh** — executor caches (e.g. a poetry venv path, including `poetry_virtualenv` injected by the poetry plugin for the root project) are project-specific |
| `ui`, `dry`, loop | shared from parent |
| `poe_active` | parent's value (the original process `POE_ACTIVE`, not the root executor's key) |
| shutdown manager | **shared** with parent — no second signal handler. Child subprocesses and async tasks register with the parent's manager, so Ctrl-C and `interrupted_exit_status` behave as for any task |
| output streaming | must reflect the parent's streaming state for the child's lifetime (a ref inside a `parallel` must keep prefixing/capturing). Either share the state or copy it at creation — builder's call, but test it inside `parallel` |
| project cache | shared reference (§4.2) |

The child context must not call `install_handler`/`restore_handler` or
`wait_for_processes` itself; the root scope owns those.

**Global executor CLI overrides apply to the child.** `--executor`/`-e` and
`--executor-opt`/`-X` are run-wide overrides: `RunContext._resolve_executor_config`
applies them to every task in the run, including the target of an in-project ref.
For consistency they also apply to tasks run in a child project. This falls out of
sharing `ui` and needs no special case. Test it (e.g. `poe -e simple check-foo`
runs foo's task with the simple executor).

**Verbosity.** The child's global `verbosity` setting becomes the baseline for the
child's tasks via the child-scoped `PoeIO(parent=self.ctx.io, baseline_verbosity=…)`
(the target task's own `verbosity` option still wins over it). Never call
`configure(baseline=…)` on the shared IO — that would change the root's output for
the rest of the run. `-v`/`-q` given on the CLI keep stacking on top, as they do for
every task; verify the offset propagates through the parent IO chain.

### 4.4 Env layering

The ref task's fully resolved env becomes the child project's **base env**, standing
in for the process env of a `poe -C` subprocess:

```
ref task env  (env.get_subprocess_env_vars(): root process env + root config env
               + ref task's own env/envfile + its args; private vars excluded)
  → TaskEnv.create(child_config, base_env=…)   POE_ROOT, POE_VERBOSITY reset for
                                               the child; POE_CWD/POE_PWD carried
                                               through unchanged (existing rule)
  → child partitions' config env/envfile        apply_env_config, as RunContext.__init__ does
  → referenced task's own env/envfile
  → referenced task's args
```

Consequences, all intended:

- The child project's config env wins over anything from the caller, including the
  ref task's own `env`. A child config var declared as `{ default = "…" }` is only
  set when absent, so the caller *can* override it — poe's existing opt-in for
  overridable vars works across projects unchanged.
- The ref task's env is the parent env of the referenced task, as with any ref.
- `POE_CONF_DIR`, envfile resolution and git vars are per the child config (child
  `EnvFileCache` is keyed on the child project dir).

The referenced task is then run with `task.run(context=child_context)` and **no**
`parent_env`, so `base_env = context.env` (the layered env above).

The alternative order (ref env above child config env) is rejected: `TaskEnv` stores
vars flat, so root config env cannot be separated from the ref task's own env, and
root config would clobber same-named child config vars (anti-goal).

### 4.5 Executing the referenced task

In `RefTask._handle_run`, when `project` is set:

1. Resolve path, get/load `LoadedProject` (errors → §5).
2. Build the child context (§4.3/§4.4).
3. Look up `ref_invocation[0]` in the child `TaskSpecFactory`; run-time checks:
   unknown task, `use_exec` target, and `capture_stdout` on a ref whose target
   cannot accept it (`accepts_option`) — each an `ExecutionError` (§5).
4. Create the task with a `TaskContext` for the child: `config` and `specs` from the
   loaded project, `cwd=str(task_spec.source.cwd)` (as `PoeThePoet.resolve_task`
   does — not the parent's cwd), `io=PoeIO(parent=self.ctx.io, baseline_verbosity=…)`,
   `ui=self.ctx.ui`. Forward `capture_stdout` as today.
5. If the task has deps, run its graph with the child context. `RefTask` already
   duplicates the app's graph loop in `_run_task_graph`; reuse it with the child
   context (extracting a shared helper is welcome but optional).
6. `ignore_fail` handling, `task_state.add_child`, `finalize` and waiting are
   unchanged.

Hidden (`_`-prefixed) target tasks are allowed, as for in-project refs (the ref is
an internal reference, like `poe` invoked internally).

### 4.5.1 Refs as the source of `uses` / `uses_env` (decided: supported)

A cross-project ref may be the source of a `uses` or `uses_env` in the calling
project, e.g. `consumer = { cmd = "echo $X", uses = { X = "check-foo" } }`.

**Existing bug this depends on (in-project refs, current code):** when a ref runs
with captured stdout, the executor saves the output under the *leaf* task's
invocation (`executor/base.py:522`, `self.context.save_task_output(self.invocation,
…)`), while the consumer looks it up under the *ref's* invocation
(`RunContext._get_dependency_values`, `context.py:211`). So `uses = { X = "r" }`
with `r = { ref = "_hi" }` fails with an unhandled `KeyError: ('r',)` from
`TaskOutputCache.get_task_output`. Reproduced on 0.49.0 during design (traceback
ends in `context.py`, `get_task_output`: `KeyError: ('r',)`).

**Fix (covers both cases):** when a ref task runs with captured stdout, after its
target completes it saves the target's captured output into the **caller's**
context under the **ref's own invocation**. For an in-project ref the caller's and
target's context are the same object; for a cross-project ref the target's output
lives in the child context's cache and is copied up. The fix for in-project refs
may land as its own commit or PR first (builder's call); either way it needs its
own regression test.

`TaskOutputCache.get_task_output` raising a bare `KeyError` is itself a gap against
the "only `PoeException`s escape" rule; hardening it to raise a helpful
`ExecutionError` is welcome but optional once the above is fixed.

At load time `accepts_option("capture_stdout")` returns `True` for a ref with
`project` (§3). If the target turns out not to accept captured stdout, the run-time
check in §4.5 step 3 reports it via §5.

## 5. Errors

All failures of a cross-project ref surface as an `ExecutionError` raised from the
ref task, with the underlying error as its cause. This keeps them out of the
`PoeException → print_help` path in `PoeThePoet._run_task` (no help dump).

Headline form: `Task {ref_task!r} could not run {target!r} in project {project_path}`
(the project path as written after templating, or relative to the root project dir).
Then one `From:` line per cause level.

| Failure | Cause line(s) |
|---|---|
| Path doesn't exist / no poe config there | `No poe configuration found from location …` |
| Child config invalid (any spec) | the `ConfigValidationError` message |
| Unknown task in child | `Unrecognized task 'chekc'` |
| Target is `use_exec` / can't accept `capture_stdout` | the same wording as the load-time checks |
| Invalid args for the target | `Invalid arguments for task 'check'` → `unrecognized arguments: --strict` |

Example:

```
Error: Task 'check-project' could not run 'check' in project packages/foo
     | From: Invalid arguments for task 'check'
     | From: unrecognized arguments: --strict
```

### 5.1 Multi-level causes

`ExecutionError` currently keeps only one level of cause (`args[0].args[0]`), a
holdover from 2020 with no evident reason. Change it to collect the whole chain of
*explicit* causes (errors passed as `args`: each wrapped `ExecutionError` /
`PoeException`'s own msg and its causes, in order), and make `PoeUi.print_error`
render one `From:` line per level. This also covers a cross-project ref into a
project whose task is itself a cross-project ref.

Scope limit: the chain walks explicit `args` causes only. The separate
`From: {__cause__!r}` line that `print_error`/`_format_poe_error` print for
`raise … from` chains is left exactly as it is — existing tests pin that repr
output (e.g. `tests/test_parallel_tasks.py`), and existing output must be
unchanged. The new cross-project errors are therefore constructed with explicit
cause args, not `raise … from`.

### 5.2 Argument errors in the target

Today `PoeTaskArgs.parse` lets argparse print its usage and error line to stderr,
then raises `ExecutionError("Invalid arguments for task …")`. For a target invoked
through a cross-project ref, argparse's usage line would name `poe check`, which
nobody ran and which would run the *root* project's `check` (anti-goal).

So for cross-project targets: don't print argparse's usage; capture argparse's error
message (`unrecognized arguments: --strict`) and attach it as the innermost cause
(§5 example). The mechanism (a flag on `TaskContext`, a capturing error stream,
a dedicated exception subclass carrying the message, …) is the builder's call.
In-project refs and CLI invocations keep today's behaviour (non-goal).

Arg errors in the *ref task's own* args (e.g. missing `project_name`) are unchanged:
the ref task's usage plus error, as for any task.

## 6. Dry run

`--dry-run` behaves as for an in-project ref: the child config is loaded (needed to
resolve the task and print what would run), and the referenced task prints its
dry-run line through the child context with `dry=True`. Loading config in dry-run
may execute `include_script` hooks of the child, exactly as `poe -C … --dry-run`
would.

## 7. Schema

The `project` field is picked up by the generator from its annotation and
docstring. Hand-edit only `RefTask.__schema_fragment__` for the `cwd`/`project`
exclusivity. Regenerate the schema with the project's poe task and add the invalid
fixture (§3).

## 8. Documentation

Keep it brief (house style: no obscure edge-case detail in user docs).

- `docs/tasks/task_types/ref.rst`: a short "Referencing a task in another project"
  section — the example from §1, one sentence on the mental model (runs with that
  project's config, env and executor), one sentence on env precedence
  (`{ default = … }` to let callers override).
- `docs/guides/include_guide.rst` (monorepo context): one line pointing to the new
  option as the way to run a subproject's task with its own venv, as distinct from
  `include`.
- Bundled skill: it must actively steer agents to this feature (operator
  requirement):
  - `references/task-types.md` `## ref`: the example and the "drop-in replacement
    for `poe -C`" framing
  - `references/task-types.md` `## cmd`: a one-line pointer for the moment an agent
    would write `cmd = "poe -C …"`
  - `references/creating-tasks.md`: a `poe -C` ❌/✅ pair under "Compose tasks; don't
    call poe recursively", plus a short `## Monorepos` section contrasting `include`
    with `ref` + `project`
  - `SKILL.md`: the task-types table's `ref` row mentions other projects
  - a skill eval (`tests/skills/evals.json`) with a monorepo fixture, pinning that
    agents use `ref` + `project` rather than `poe -C`

  Do **not** bump `version.txt` (release-only).

## 9. Tests

Follow `tests/README.md` and local style; use `run_poe`. Suggested fixture:
`tests/fixtures/monorepo_project/` with a root config and two subprojects
(`packages/foo`, `packages/bar`), each with its own `env`/`envfile` and tasks named
the same as root tasks (to catch namespace mix-ups). Cover at least:

- literal and templated `project`; directory and config-file forms; extra args via
  `--`
- env layering: child config overrides caller; child `{ default = … }` overridden by
  caller; ref task env reaches the target; `POE_ROOT`/`POE_CONF_DIR` are the child's,
  `POE_PWD` is the caller's
- the child's executor config is used (e.g. root and child configure different
  executors)
- target with deps and with `uses` (graph runs in child; outputs don't collide with a
  same-named root task)
- a root task with `uses`/`uses_env` sourced from a cross-project ref, and (as a
  regression test for the existing bug) from a plain in-project ref
- `capture_stdout`, `ignore_fail`, `--dry-run`, and a cross-project ref inside a
  `parallel` (output prefixing still works)
- the same project referenced twice in one run is loaded once (cache)
- each error row in §5, including multi-level causes and the arg-error output with
  no argparse usage line
- load-time: `cwd` + `project` rejected; a `project` ref to a non-existent task does
  **not** fail at load time

## 9a. Implementation approach: duplicate, then consolidate

Operator's direction: in a first pass, duplicate what `RefTask` needs from
`PoeThePoet` rather than designing shared abstractions up front. In a second pass,
once the overlap and the real degrees of freedom are visible, consolidate.

What actually needs duplicating is small, since most of `PoeThePoet` is CLI work
(argv, help, version, broken pipe, mapping errors to exit codes):

| Piece | In `PoeThePoet` | Cross-project ref needs |
|---|---|---|
| Load project | `_call`: `PoeConfig.load` + validate all specs | different path source; lazy validation; errors wrapped |
| Build the task | `resolve_task`: `TaskContext` construction | same shape, IO parented to the ref's IO |
| Run, with or without deps | `_run_task` / `_run_task_graph` | already duplicated as `RefTask._run_task_graph` |
| Run context | `run_context` → `RunContext.scope` (root) | genuinely new: a child that shares the root's shutdown handling |

Guardrails for pass 1:

- Put the duplicated code in one place that pass 2 can *move* rather than untangle,
  e.g. private helpers in `task/ref.py` or a small module of their own, not inline
  in `_handle_run`.
- Land the full test suite in pass 1, so pass 2 is a refactor checked against the
  same tests.

The degrees of freedom pass 2 must preserve:

- where the config path comes from (`-C`/cwd vs the `project` option)
- validation scope (all specs vs on lookup)
- the error sink (help text and exit code vs raising `ExecutionError` to the caller)
- who owns the run context (root scope vs a child sharing shutdown)

The likely outcome is a "loaded project" unit (config, specs, validation policy) and
a "run this task in this context" function that raises errors. `PoeThePoet` would
wrap that function with its own help and exit-code handling. Both passes may be
separate commits in the same PR, or pass 2 may follow as its own PR.

## 10. Left to the builder

- Names (`LoadedProject`, `RunContext.for_project`) and where `LoadedProject` lives.
- Whether to extract the shared graph-execution loop from `PoeThePoet` / `RefTask`.
- Mechanism for §5.2 argparse capture and for sharing output-streaming state.
- Exact headline wording, as long as it names the ref task, the target task and the
  project.

## 11. Calls made during design (not explicitly confirmed by the operator)

- `project` resolves like the `cwd` option (relative to the project root).
- Child task specs are validated lazily, on first lookup (operator asked for this).
- Hidden target tasks are allowed.
- `poe_active` for the child is the original process value.
- `--executor`/`-X` CLI overrides reach the child project, as they reach in-project
  ref targets.
- The `uses`-from-ref bug fix ships in the same PR (operator decision).
- The cause chain walks explicit `args` causes only; `__cause__` repr lines unchanged.
- The child config's `verbosity` is a baseline for its tasks only, via a scoped IO.
