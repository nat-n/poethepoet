# `uses_env` Task Option — Implementation Plan

> **For agentic workers:** implement task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking. Run `poe lint`, `poe types`, and `poe format` as you go;
> finish with `poe check`.

**Goal:** Add a `uses_env` task option that runs upstream task(s), parses each
one's stdout as an env file (dotenv syntax), and merges the resulting variables
into the host task's environment — a list-shaped sibling to `uses` for importing
zero-or-more variables from a single subtask.

**Architecture:** Reuse the existing `uses` execution machinery
(`_get_upstream_invocations` → `iter_upstream_tasks` → graph capture →
`get_task_env` merge). The only genuinely new pieces are (a) a
`collapse_whitespace` knob on `get_task_output` so raw stdout (with newlines
intact) can be retrieved, and (b) parsing that raw stdout with the existing
`env/parse.py:parse_env_file`, merging against the current task env.

**Spec reference:** `docs/superpowers/specs/2026-06-28-uses-env-task-option-design.md`.

**Branching:** Branch `claude/uses-env-task-option-jgvk5w` (from `development`).

---

## Files touched

**Production:**

- `poethepoet/task/base.py` — new `uses_env` field + docstring on `TaskOptions`;
  validation in `_base_validations`; `"uses_env"` in `_get_upstream_invocations`;
  `iter_upstream_tasks` yields `uses_env` tasks; `has_deps` includes `uses_env`;
  `run` dry-run + raw-output retrieval; `get_task_env` parses + merges.
- `poethepoet/context.py` — `collapse_whitespace` param on
  `ContextProtocol.get_task_output`, `RunContext.get_task_output`,
  `TaskOutputCache.get_task_output` (and any sibling context class); new
  `_get_dep_env_outputs` helper.
- `docs/_static/partial-poe.json` — regenerated.

**Docs / skill:**

- `docs/tasks/options.rst`
- `docs/guides/composition_guide.rst`
- `poethepoet/skills/poethepoet/references/task-options.md`
- `poethepoet/skills/poethepoet/version.txt` (bump)

**Tests:**

- `tests/fixtures/graphs_project/pyproject.toml` — fixture tasks.
- `tests/test_graph_execution.py` — behaviour tests.

---

## Task 1 — `collapse_whitespace` knob on output retrieval

- [ ] In `poethepoet/context.py`, add `collapse_whitespace: bool = True` to
      `TaskOutputCache.get_task_output`; when `False`, return the stored raw
      string unmodified (skip both the `strip("\r\n")` and the
      `re.sub(r"\s+", " ", …)` collapse).
- [ ] Thread the same parameter through `RunContext.get_task_output` (delegating
      to the cache) and any other context class exposing it.
- [ ] Update the `ContextProtocol.get_task_output` signature to include the param.
- [ ] Confirm existing callers (`_get_dep_values`) still pass nothing and get the
      collapsing default. No behaviour change for `uses`.

## Task 2 — context helper for raw `uses_env` outputs

- [ ] Add `_get_dep_env_outputs(self, invocations: Sequence[tuple[str, ...]]) ->
      list[str]` to the context, returning
      `[self.get_task_output(inv, collapse_whitespace=False) for inv in invocations]`.
      (Sibling to `_get_dep_values`, ordered to match the `uses_env` list.)

## Task 3 — `uses_env` option field

- [ ] Add to `PoeTask.TaskOptions` (`task/base.py`), after `uses`:
      `uses_env: str | Sequence[str] = ()` with a ≥3-line class-attribute
      docstring describing env-file parsing and the "zero or more variables"
      semantics. (Backfill/description tests require the docstring.)

## Task 4 — upstream-invocation resolution + graph wiring

- [ ] In `_get_upstream_invocations`, add a `"uses_env"` key: a list of
      invocation tuples built by template-filling + `shlex.split` each entry,
      normalizing a bare `str` to a one-element list.
- [ ] In `iter_upstream_tasks`, after the `uses` loop, yield
      `("", self._instantiate_dep(invocation, capture_stdout=True))` for each
      `uses_env` invocation.
- [ ] In `has_deps`, include `self.spec.options.get("uses_env", False)`.

## Task 5 — `get_task_env` parse + merge

- [ ] Add `uses_env_outputs: Sequence[str] | None = None` param to
      `TaskSpec.get_task_env`.
- [ ] After `result = parent_env.clone(...)` and **before** the existing
      `uses_values` update, if `uses_env_outputs`: lazily
      `from ..env.parse import parse_env_file` and, for each output in order,
      `result.update(parse_env_file(output, base_env=result))`.
- [ ] Keep the existing `uses_values` update immediately after, so `uses` wins on
      collision.

## Task 6 — `run` dry-run + wiring the outputs through

- [ ] In `run`, extend the dry-run early-return to also fire when
      `upstream_invocations.get("uses_env")`, emitting an analogous "unresolved
      dependency task results via uses_env option for task '…'" notice. Emit it
      as a separate action from the `uses` notice so the existing
      `test_uses_dry_run` assertion text is unchanged.
- [ ] In the real-run path, compute
      `uses_env_outputs = context._get_dep_env_outputs(upstream_invocations["uses_env"])`
      and pass it into `get_task_env` alongside `uses_values`.

## Task 7 — validation

- [ ] In `TaskSpec._base_validations`, add a block mirroring the `uses` block
      (minus the env-var-key check) for `self.options.uses_env`: for each resolved
      task name, error if unknown, if `use_exec` is set, or if `capture_stdout` is
      set. Normalize the `str | Sequence[str]` shape before iterating.

## Task 8 — schema regeneration

- [ ] Run `poe schema-build` to regenerate `docs/_static/partial-poe.json`;
      confirm `uses_env` appears with its description and `str | array` type.
- [ ] Run `poe schema-check` (parity/drift) and the schema test suite; no new
      fragment or invalid-corpus fixture is expected (cross-task constraints are
      runtime-only, as with `uses`).

## Task 9 — tests

- [ ] In `tests/fixtures/graphs_project/pyproject.toml`, add tasks covering:
      a producer emitting multiple `KEY=value` lines; a host using
      `uses_env = "_producer"`; multi-entry `uses_env`; a private (`_lower`) var in
      the output; collision precedence with `uses`; and an `export `-prefixed
      producer (motivating case). Reuse `poe_test_echo` / `poe_test_env` helpers
      per existing fixture style.
- [ ] In `tests/test_graph_execution.py`, add tests paralleling the existing
      `test_uses_*` cases: happy-path multi-var import; newlines preserved (parses
      into distinct vars, not collapsed); list-order override; `uses` overrides
      `uses_env` on collision; private-var filtering from subprocess env; dry-run
      notice; empty/comment-only output is a no-op.
- [ ] Add a validation test (unknown task / `capture_stdout` / `use_exec`
      referenced via `uses_env` raises `ConfigValidationError`), matching how
      `uses` validation is tested.

## Task 10 — documentation + skill

- [ ] `docs/tasks/options.rst`: add a `uses_env` table entry beside `uses`.
- [ ] `docs/guides/composition_guide.rst`: add a short `uses_env` example (the
      credential-import case) and an `.. important::` note that, unlike `uses`,
      output is parsed as an env file (not whitespace-collapsed).
- [ ] `poethepoet/skills/poethepoet/references/task-options.md`: add a `uses_env`
      section paralleling `uses`.
- [ ] Bump `poethepoet/skills/poethepoet/version.txt`.

## Task 11 — finalize

- [ ] `poe format`, then `poe check` (style, types, lint, tests) green.
- [ ] Commit on `claude/uses-env-task-option-jgvk5w` with a descriptive message;
      do not open a PR unless asked.

---

## Notes / decisions baked in (from the spec)

- `base_env` for parsing is the **current task env** (consistent with `envfile`).
- Precedence: `uses_env` applied in list order (later wins), then `uses` on top.
- Both applied before `apply_env_config`, matching the existing `uses` placement.
- Private-var handling is automatic (name-based) — no extra code.
- Pre-existing `task-options.md` precedence-wording discrepancy is **out of
  scope** and parked.
