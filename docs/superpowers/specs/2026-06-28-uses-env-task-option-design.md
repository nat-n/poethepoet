# `uses_env` Task Option — Design

**Status:** Drafted 2026-06-28, pending review.
**Author:** Design produced collaboratively with Claude.

## 1. Goals and scope

### Primary goal

Add a new task option, `uses_env`, that runs one or more upstream tasks, captures
each one's stdout, parses it with env-file (dotenv) syntax, and merges the
resulting variables into the host task's environment.

It is a sibling to the existing `uses` option. The difference:

- `uses` is a `map of var-name → task`: the host author names a single variable,
  and the (whitespace-collapsed) stdout of the referenced task becomes that
  variable's value.
- `uses_env` is a `list of tasks`: each referenced task's stdout is parsed as an
  env file, so a single subtask can yield **zero or more** variables, which the
  subtask names itself.

### Motivating use case

Importing several credentials from a single credential-broker invocation, e.g.:

```toml
[tool.poe.tasks._aws-creds]
shell = "aws-vault exec my-profile -- env | grep '^AWS_'"

[tool.poe.tasks.deploy]
cmd = "terraform apply"
uses_env = "_aws-creds"
```

Here `_aws-creds` emits multiple `AWS_*=…` lines in one shot; `uses` cannot
express "import all of these" because it requires one named key per variable.

### In scope

- New `uses_env: str | Sequence[str]` field on `PoeTask.TaskOptions`.
- Runtime wiring: upstream-invocation resolution, graph execution with stdout
  capture, raw (non-collapsed) output retrieval, env-file parsing, env merge.
- A `collapse_whitespace: bool = True` parameter threaded through the
  `get_task_output` call chain so `uses_env` can read raw stdout while `uses`
  keeps its current whitespace-collapsing behaviour.
- Validation mirroring `uses` (referenced task exists, is not `use_exec`, does not
  set `capture_stdout`).
- Dry-run handling (same "unresolved dependency" notice as `uses`).
- Schema regeneration (`partial-poe.json`) — the field is picked up automatically
  by the generator from its type + docstring.
- User docs (`docs/tasks/options.rst`, `docs/guides/composition_guide.rst`),
  bundled skill reference (`task-options.md`) and skill `version.txt` bump.
- Tests under `tests/` (graph execution + fixtures).

### Out of scope

- Any change to `uses` semantics or its whitespace-collapsing behaviour.
- A namespacing/prefix variant (e.g. a map form whose key prefixes imported
  vars). The subtask already names its own vars; if prefixing is wanted the user
  controls it in the subtask. Can be revisited if demand appears.
- Resolving the pre-existing doc/precedence wording discrepancy between
  `task-options.md` ("task env → uses outputs") and the code (which applies
  `uses` values *before* task `env`/`envfile`). Parked deliberately; tracked
  separately.

## 2. Naming decision

The option is `uses_env` (snake_case), consistent with **100%** of poe's own task
and global option names (`capture_stdout`, `use_exec`, `ignore_fail`,
`default_item_type`, `output_mode`, `print_result`, `empty_glob`,
`default_task_type`, `include_script`, `shell_interpreter`, …).

The only dash-delimited option keys in the codebase are the `uv` executor options
(`no-group`, `no-sync`, `no-project`, `with` in `executor/uv.py`), which mirror
uv's *own CLI flag spelling* via `Metadata(config_name=…)`. That is external-tool
fidelity, not a poe style. `uses_env` is a native poe option, so it follows poe's
underscore convention. Note: option keys are matched **exactly** (no
dash↔underscore normalization — `options/base.py`), so the spelling is
load-bearing.

`uses_envfile` was considered and rejected: poe's `envfile` option implies a file
on disk, but here the input is task stdout, so the name would import the wrong
mental model.

## 3. Option shape and semantics

### Field

```python
uses_env: str | Sequence[str] = ()
```

- A single string is one task invocation; a sequence is several, applied in order.
- Each entry is a task invocation string, template-resolved and `shlex.split` the
  same way as `deps` / `uses` entries (so it supports args and parameter
  expansion, e.g. `uses_env = "creds ${profile}"`).

### Parsing

Each captured stdout string is parsed via the existing
`poethepoet/env/parse.py:parse_env_file(content, base_env)`.

- `parse_env_file` already handles a leading `export ` prefix and `KEY=value`
  lines, and supports `${VAR}` / `${VAR:-default}` expansion against `base_env`
  — verified against the motivating `aws-vault … | env` output shape.
- **`base_env` is the current task env** (decided): imported values may reference
  variables already in scope, consistent with how the `envfile` option resolves
  (`task_env.py:apply_env_config` passes `base_env=self`).

### Merge order and precedence

In `get_task_env`, applied at the **same point** as the existing `uses` values
(immediately after the parent env is cloned, *before* `apply_env_config`), so
task `env`/`envfile` templates can reference imported vars:

1. For each `uses_env` entry, in list order, parse and `result.update(...)`. Later
   entries override earlier ones; each entry's parse sees the parent env plus
   variables imported by earlier entries (`base_env=result`).
2. Then apply `uses` values on top — explicit per-key `uses` wins over bulk
   `uses_env` import on a name collision (decided).

### Private variables

No special handling required. The private-var mechanism is purely name-based
(`task_env.py:set`/`update`: `_`-prefixed with no uppercase ⇒ private), so an
imported variable named `_token` is automatically kept out of the subprocess
environment while remaining available for templating — identical to `uses`.

## 4. Execution wiring

Mirrors the existing `uses` path in `poethepoet/task/base.py` and
`poethepoet/context.py`:

- **`_get_upstream_invocations`** gains a `"uses_env"` list of invocation tuples
  (template-filled + `shlex.split`), alongside `"deps"` and `"uses"`.
- **`iter_upstream_tasks`** yields `("", task)` for each `uses_env` invocation with
  `capture_stdout=True`. The `key` is unused by graph construction
  (`graph.py:108` registers by `task.invocation`), so `""` is fine for multiple
  entries, exactly as with `deps`.
- **`has_deps`** returns `True` when `uses_env` is set, so the graph layer engages.
- **`run`**: in dry-run, if `uses_env` invocations exist, print the same
  "unresolved dependency task results" notice used for `uses` (separate emit so
  the existing `uses` dry-run test text is unchanged), then return early. In a
  real run, fetch the raw captured outputs and pass them to `get_task_env`.

### Raw output retrieval — the one real gotcha

`TaskOutputCache.get_task_output` collapses whitespace
(`re.sub(r"\s+", " ", …strip("\r\n"))`), which would destroy the newlines
env-file parsing depends on. We add a single knob rather than a second method:

```python
def get_task_output(self, invocation, collapse_whitespace: bool = True) -> str:
    raw = self._captured_stdout[invocation]
    if not collapse_whitespace:
        return raw
    return re.sub(r"\s+", " ", raw.strip("\r\n"))
```

- The parameter is threaded through `ContextProtocol.get_task_output`,
  `RunContext.get_task_output`, and any other context implementation, defaulting
  to `True` so all current callers (`_get_dep_values`) are unaffected.
- A new helper on the context — `_get_dep_env_outputs(invocations) -> list[str]`
  — returns the raw stdout for each `uses_env` invocation via
  `get_task_output(inv, collapse_whitespace=False)`. Parsing happens in
  `get_task_env` (which owns the env being built and thus the `base_env`).

### `get_task_env` signature change

```python
def get_task_env(self, parent_env, io, uses_values=None, uses_env_outputs=None):
    result = parent_env.clone(io=io)
    if uses_env_outputs:
        for output in uses_env_outputs:
            result.update(parse_env_file(output, base_env=result))
    if uses_values:
        result.update(uses_values)
    ...
```

`parse_env_file` is imported lazily inside the method (CLI-startup discipline);
it is only reached when `uses_env_outputs` is non-empty.

## 5. Validation

In `TaskSpec._base_validations`, mirror the `uses` block minus the env-var-key
check (there is no key). For each resolved `uses_env` task name:

- referenced task must exist;
- referenced task must not set `use_exec`;
- referenced task must not set `capture_stdout`.

These are cross-task, runtime-only constraints — exactly like `uses`, they are
**not** expressible in JSON Schema, so no schema fragment encodes them and no
`tests/schema/fixtures/invalid/` case is added for them (consistent with how
`uses` cross-task validation is handled today).

## 6. Schema

`uses_env: str | Sequence[str]` with a class-attribute docstring is picked up
automatically by the generator (same path as `deps` / `envfile`), so the only
schema action is **regenerating `docs/_static/partial-poe.json`** via
`poe schema-build` and committing it. No new `__schema_fragment__` or
`fragments.py` change. The schema-parity drift check (`poe schema-check`) and the
description-backfill test guard correctness.

## 7. Documentation

- `docs/tasks/options.rst`: add a `uses_env` entry to the options table next to
  `uses`, noting env-file parsing and that one task can yield several variables.
- `docs/guides/composition_guide.rst`: a short subsection / example showing the
  credential-import use case, and an `.. important::` note that — unlike `uses` —
  output is **not** whitespace-collapsed (it is parsed as an env file).
- `poethepoet/skills/poethepoet/references/task-options.md`: a `uses_env` section
  paralleling the existing `uses` section.
- `poethepoet/skills/poethepoet/version.txt`: bump (user-facing surface changed).

## 8. Risks / notes

- **Lazy vars in `base_env`:** `TaskEnv` is Mapping-compatible but iterating it for
  `{**base_env}` surfaces only resolved `_env_vars`, not unresolved lazy vars.
  This matches the existing envfile-resolution behaviour and is an acceptable
  edge limitation; `${VAR}` references in imported env output will resolve against
  already-realized vars. Documented, not engineered around.
- **Encoding:** raw retrieval reuses the cache's already-decoded string (the
  existing `PYTHONIOENCODING` fallback at decode time still applies); no new
  decoding path.
- **Empty / comment-only output:** parses to zero variables — a no-op merge, which
  is the intended "zero or more" behaviour.
