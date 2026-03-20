# Agent Guide

Poe the Poet is a task runner for Python projects that integrates with poetry and uv.

## Use poe tasks

This project uses poethepoet to manage development tasks. Prefer to use poe tasks when available to reduce friction.

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

**Lazy imports** are use strategically with the goal of reducing latency, since this is a CLI app

## Where to Look

| To do this...                     | Look here                          |
|-----------------------------------|------------------------------------|
| Add a new task type               | `task/base.py`, then `task/*.py`   |
| Add a new executor                | `executor/base.py`                 |
| Modify CLI behavior               | `ui.py`, `app.py`                  |
| Change config parsing             | `config/config.py`                 |
| Add environment variable handling | `env/manager.py`                   |
| Fix shell completion              | `completion/`                      |

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
- This is a CLI, so be mindful of performance concerns
- `poe lint` and `poe types` must pass
- `poe format` should be run to ensure correct formatting

## Development tasks

- This project uses poe tasks to manage project tasks. Always check if there is an applicable poe task for a common action, e.g. running servers, tests or other quality checks.
