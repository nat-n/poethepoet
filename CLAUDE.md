# Agent Guide

Poe the Poet is a task runner for Python projects that integrates with poetry and uv.

## Set up your environment first (do this before running anything)

This repo is a **Poetry** project, and the package it builds *is* poethepoet
itself. Two distinct installs are in play — keep them straight:

1. **Sync the project venv** — this is where tests and checks actually execute:
   ```bash
   poetry sync
   ```
   It installs the project plus the **locked** dev dependencies (black, ruff,
   mypy, pytest, …) at their pinned versions. Those pins are load-bearing:
   formatting and schema-generation output differ across tool versions, so
   anything installed another way produces drift and false failures.

2. **Install a released `poe` globally**, as a stable task runner — *separate*
   from the in-development Poe in the project venv:
   ```bash
   pipx install poethepoet
   ```
   You are editing poethepoet, so don't drive your own checks with the code
   under test. Run from the repo root, this global `poe` reads the project's
   `[tool.poe.tasks]` and executes each task **inside the Poetry venv** (its
   auto/poetry executor), so checks still run against the locked deps.

3. **List the tasks** as your first step of exploration:
   ```bash
   poe          # shows every task with its description
   ```

**If a tool ever seems "missing," the fix is `poetry sync` — never `pip
install` into the system Python.** Ad-hoc installs pull unpinned versions and
silently corrupt formatting/schema results.

## Use poe tasks

This project uses poethepoet to manage development tasks. After the setup above, run everything through poe tasks — `poe check`, `poe test`, `poe lint`, `poe types`, `poe format`.

Run `poe` to see available tasks and their descriptions.


```bash
poe check             # run all quality checks (style, types, lint, tests) - this takes a while.
poe test              # run full test suite
poe test-quick        # skip slow/flaky tests
poe format            # auto-format code (ruff + black)
poe lint              # ruff linting only
poe types             # mypy type checking
```

**Tip:** cmd tasks (like test or test-quick) pass extra args to the underlying command, so you can run specific tests:
```bash
poe test tests/test_script_tasks.py -k "test_running"
poe test-quick -x  # stop on first failure
```

### Testing

Run tests with:

```sh
poe test [extra pytest arguments]
```

Reference tests/README.md for instructions on how to write, run, and debug tests in this project.

## Key Patterns

**Task types** use a metaclass registry (`task/base.py:MetaPoeTask`). Each task type:
- Inherits from `PoeTask`
- Sets `__key__` and `__content_type__` class attributes
- Implements `_handle_run()` for execution logic

**Executors** follow the same pattern (`executor/base.py:MetaPoeExecutor`).

**Config loading** is async-first. See `config/config.py:PoeConfig`.

**Type hints** are used throughout. Circular imports are avoided with `TYPE_CHECKING` guards.

**Lazy imports** are used strategically with the goal of reducing latency, since this is a CLI app. Note the distinction: imports only needed for type annotations belong in a `TYPE_CHECKING` block (with `from __future__ import annotations` at the top of the module), not as lazy runtime imports inside functions.

## Where to Look

| To do this...                     | Look here                          |
|-----------------------------------|------------------------------------|
| Add a new task type               | `task/base.py`, then `task/*.py`   |
| Add a new executor                | `executor/base.py`                 |
| Modify CLI behavior               | `ui.py`, `app.py`                  |
| Change config parsing             | `config/config.py`                 |
| Add environment variable handling | `env/manager.py`                   |
| Fix shell completion              | `completion/`                      |
| Edit the bundled Agent Skill      | `poethepoet/skills/poethepoet/`    |

## Bundled Agent Skill

This project ships an Agent Skill at `poethepoet/skills/poethepoet/` that teaches AI coding assistants how to use poe. End-users install it via `poe _install_skill`, which copies the tree into a detected `.claude/skills/`, `.codex/skills/`, etc. (see `poethepoet/skills/install.py`).

- **Skill content**: `SKILL.md` + `references/*.md` (task-types, task-options, args-reference, creating-tasks, task-packages).
- **Pinned version**: `poethepoet/skills/poethepoet/version.txt` — kept in step with poe's user-facing surface. Bump it when skill content changes meaningfully.
- **Evals**: `tests/skills/evals.json` (corpus) and `tests/skills/run_evals.py` (runner). The runner copies the skill into a fixture project's `.claude/skills/` and shells out to `claude -p`, so it exercises the real discovery path. Run via `poe eval-skill`.

When you change poe's behaviour, syntax, or user-facing semantics, check whether the skill's reference docs still describe it correctly — drift here causes downstream agents to hedge or generate broken configs. If you spot a gap while working on the skill, the canonical answer is in the installed source (`poethepoet/task/*.py`) and the published docs (https://poethepoet.natn.io); verify before paraphrasing.

## Test Fixtures

Tests use fixture projects in `tests/fixtures/*_project/`. The `run_poe` fixture is the main way to invoke poe in tests, or `run_poe_subprocess` if necessary - see `tests/conftest.py`.

## Branching

- Branch from `development` for features/bugfixes
- Branch from `main` only for docs or hotfixes

## Development process

- The user docs are in the repo and good source of context on how the product is meant to work.
- When writing tests, observe and replicate local testing style.
- When introducing new patterns or making any kind of contribution to architecture present the plan for operator review before making change to code.

### Code style

- Don't use single character variable names
- Do use the walrus operator whenever applicable
- docstrings must always use three lines minimum: opening `"""` alone on its own line, content, closing `"""` alone on its own line — never `"""text"""` on one line
- Use **relative imports** for everything inside the `poethepoet` package — `from ..task.base import PoeTask`, not `from poethepoet.task.base import PoeTask`. Applies to top-level, `TYPE_CHECKING`, and lazy-inside-function imports alike. Sole exception: `poethepoet/__main__.py` keeps `from poethepoet import main` so it works whether invoked via `python -m poethepoet` or as a direct script.
- This is a CLI, so be mindful of performance concerns
- `poe lint` and `poe types` must pass
- `poe format` should be run to ensure correct formatting
- `PoeOptions` fields use class-attribute docstrings (PEP 257-style) placed immediately after the annotation. These are extracted by `PoeOptions.description_for_field()` and consumed by the JSON Schema generator, so every field on a `PoeOptions` subclass should have one — the description backfill tests catch gaps. Example:
  ```python
  class TaskOptions(PoeOptions):
      cwd: str | None = None
      """
      Working directory the task runs in. Relative to the project root unless absolute.
      """
  ```

### Schema/runtime validation parity

Runtime validation and the generated JSON Schema (`poethepoet/schema/`) are kept in parity by `tests/schema/test_invalid_corpus.py` ("if the runtime rejects it, the schema should too"). When you add or change validation in `PoeOptions.validate()`, `_task_validations`, or `PoeOptions.parse`:

- prefer expressing simple constraints (pattern, min/max, length, item count, etc.) via `Annotated[T, Metadata(...)]` on the field — `PoeOptions.parse` enforces these at runtime AND the schema generator picks them up from the same annotation, so parity is automatic. Reserve bespoke `validate()` overrides for cross-field rules or constraints that don't fit `Metadata`.
- when bespoke validation is needed, update the matching `__schema_fragment__` (or generator logic) to encode the same constraint
- add a fixture to `tests/schema/fixtures/invalid/` with a `# expected_error:` header so the parity test pins the new case
- check `tests/schema/test_mutation.py` for intentional structural gaps before assuming any mismatch is a bug

## Development tasks

- This project uses poe tasks to manage project tasks. Always check if there is an applicable poe task for a common action, e.g. running servers, tests or other quality checks.

## Agent behavior

- If you see something, say something. Always report potential bugs if you spot them, especially in new code.
