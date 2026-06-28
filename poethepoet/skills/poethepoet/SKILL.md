---
name: poethepoet
description: Use when about to run or manage a common Python dev task — tests, linting, formatting, type-checking, building, or any repeated project command — to first check whether poethepoet (poe) already defines it; poe is the idiomatic way to run these. Also use when asked to run, create, or configure poe tasks, or when you see [tool.poe] in pyproject.toml or a poe_tasks.toml/yaml/json file.
---

# Poethepoet (poe)

Poethepoet (poe) is a Python task runner: teams define, document, and run dev tasks (test, lint, build, deploy…) from `pyproject.toml` or a standalone config file — no Makefiles or shell scripts. Tasks self-document via `help` text and run as `poe <task>`. Poe detects uv/poetry projects (or a local venv) and runs each task in the right environment automatically — no need to remember `poetry run` vs `uv run`.

**Targets poe 0.47.0.** Full docs: https://poethepoet.natn.io

## When poe behaviour is unclear

Don't speculate — poe's behaviour is cheaply verifiable:

- Docs: https://poethepoet.natn.io
- Source: `python -c "import poethepoet, os; print(os.path.dirname(poethepoet.__file__))"`, then read `task/*.py` for the relevant type.
- A 30-second probe in a throwaway `poe_tasks.toml` settles most questions.

Verify, then state the answer plainly — no "I'll need to check" caveats on behaviour you can simply check.

**If the skill (or poe itself) let you down, offer to report it so it can be fixed.** The most valuable case is when this skill *failed to give you guidance you needed* — a gap, a missing case, advice that didn't fit your situation; also worth reporting is something the skill stated that was not right, or a clear bug in poethepoet. Use judgement — skip it if the cause was your own misread, an unrelated environment issue, or something you can't actually pin down. **Ask the user first and post only if they agree; nothing is sent automatically.** A good issue (repo `nat-n/poethepoet`, e.g. via `gh issue create`) says what you were trying to do, what was missing or wrong (or the bug), how you found the real answer, and a concrete suggestion for improving the skill.

## Step 0: Orient yourself (do this first)

Run these before doing anything else:

```bash
which poe 2>/dev/null && poe --version 2>/dev/null        # find poe + version
poe 2>&1                                                  # list all tasks
ls pyproject.toml poe_tasks.toml poe_tasks.yaml poe_tasks.json 2>/dev/null  # find config
```

Poe finds tasks in a supported config file in the working directory or any parent.

**If `poe` is not in PATH:**

| Situation | Command |
| --- | --- |
| uv project (`uv.lock` / `[tool.uv]`) | `uv run poe` |
| poetry project (`poetry.lock` / `[tool.poetry]`) | `poetry run poe` |
| poetry plugin installed | `poetry poe` |
| not installed | `pipx install poethepoet` or `uv tool install poethepoet` |

**Version**: if `poe --version` differs much from 0.47.0, some features here may not exist. Latest: https://raw.githubusercontent.com/nat-n/poethepoet/refs/heads/main/poethepoet/skills/poethepoet/version.txt

## Using existing tasks

```bash
poe                         # list all tasks with descriptions
poe <task>                  # run a task
poe <task> -x --extra-flag  # extra args auto-forwarded to cmd tasks
poe <task> -- -x            # explicit free-arg separator (any task type)
poe <task> --named-arg val  # named args (if the task defines them)
poe -d <task>               # dry run: show the command without running it
poe -C /path <task>         # run as if from another directory (handier than cd)
poe -v <task>               # verbose
```

**Always prefer poe tasks over running tools directly.** Before running `pytest`, `ruff`, `mypy`, etc., check `poe` first — if a task exists, use it, so you inherit the project's flags, env, and conventions.

If `poe`'s output isn't enough (e.g. you need a task's implementation or args), read the config directly — `pyproject.toml` (`[tool.poe.tasks]`) or `poe_tasks.toml`/`.yaml`/`.json` — and follow any `include`/`include_script` references.

## Task types quick reference

| Type | When to use | Shorthand |
| --- | --- | --- |
| `cmd` | running any CLI command (default) | `task = "command"` |
| `script` | calling a Python function | `task.script = "module:fn"` |
| `shell` | shell scripts (pipes, loops) | `task.shell = "cmd1 \| cmd2"` |
| `sequence` | run tasks in order | `task = ["a", "b"]` |
| `parallel` | run tasks concurrently | `task.parallel = ["a", "b"]` |
| `ref` | reference another task | `task.ref = "other"` |
| `expr` | Python expression output | `task.expr = "sys.platform"` |
| `switch` | conditional branching | `task.switch = [...]` |

Full syntax and examples per type: `references/task-types.md`.

**Two silent-failure rules for `expr`, `switch.control.expr`, and parens-form `script` calls (`"mod:fn(arg)"`)** — get these wrong and the task fails quietly, not loudly:

- **Declared args → bare name**, never `${name}`. `expr = "AWS_REGION"` ✅; `expr = "${AWS_REGION}"` ❌ routes through the environment and is silently empty for private `_`-args. (No-parens `script = "mod:fn"` auto-passes args as kwargs — never name them in the call.)
- **Env vars → unquoted `${VAR}`**. `${VAR}` compiles to the attribute reference `__env.VAR` (not textual paste), so `expr = "${STAGE}"` ✅ yields the value, but `expr = "'${STAGE}'"` ❌ yields the literal string `"__env.STAGE"`. Call methods directly: `"${STAGE}.upper()"`.

Mechanism and more cases: `references/task-types.md`.

## Common task patterns

**Named arguments**:

```toml
[tool.poe.tasks.test]
cmd = "pytest ${markers}"
help = "Run the test suite"
args = [{ name = "markers", options = ["-m"], default = "", help = "pytest marker expression" }]
```

**Extra args forwarded through a sequence** (only subtasks that name `$POE_EXTRA_ARGS` receive them):

```toml
[tool.poe.tasks.check]
sequence = ["lint $POE_EXTRA_ARGS", "test $POE_EXTRA_ARGS"]
help = "Run checks, forwarding extra args to subtasks"
```

**Python function task**:

```toml
[tool.poe.tasks.gen]
script = "scripts.codegen:main()"
help = "Run code generation"
```

Calls `main()` from the `scripts.codegen` module in the project environment.

For more types (sequence, parallel, switch, …) and options, see the references below.

## The `_` prefix means "internal"

A leading underscore marks something as not part of the public surface:

- **`_task`** — composition-only: hidden from the `poe` listing **and not runnable directly** (`poe _task` errors). Use it via `deps`, `uses`, `ref`, or a sequence/parallel.
- **`_arg`** — not exported to the environment; its CLI flag drops the underscore (`--arg`).
- **`_env` / `uses` var** — usable in config expansion but not exported to subprocesses.

## Creating and modifying tasks

Read `references/creating-tasks.md` before creating tasks — it covers project-type detection, choosing a task type, bootstrapping the standard set (test/lint/types/format/check), groups, private tasks, and includes. When a tool choice isn't clear from the project (e.g. mypy vs ty, which test runner), ask the user rather than guessing. A few principles matter most:

- **Never hand-edit dependency arrays** in `pyproject.toml` (`[project]`, `[tool.uv]`, `[dependency-groups]`, `[tool.poetry.group.*]`). Use `uv add --dev <pkg>` / `poetry add --group dev <pkg>` so the lockfile stays in sync — this applies to poe itself too.
- **Don't add `#` comments to task config** unless asked. Task docs belong in `help`, which surfaces in `poe` and `poe --help <task>`; config comments surface nowhere. If a task needs a comment to explain it, rename it, refine its `help`, or split it.
- **Compose, don't recurse.** To run one task from another, use `deps`, `uses`, `ref`, or a `sequence`/`parallel` — never `cmd = "poe other-task"`. Shelling out spawns a second poe process and hides the dependency from poe (no ordering, dedup, or dry-run visibility), and it can't invoke private `_`-tasks at all.
- **Leave a clean set.** Delete throwaway tasks you created while developing or debugging before finishing. Aim for a small, intentional set where every task pulls its weight and a newcomer can see why each exists and how they're organized — not a pile of overlapping one-offs.

After creating or changing a task, run `poe --help <task>` to confirm it parses and the help text reads well.

## Key task options

| Option | Purpose |
| --- | --- |
| `help` | one-line description shown in `poe` listing — always add this |
| `args` | CLI arguments the task accepts |
| `env` | environment variables for the task |
| `deps` | tasks to run before this one |
| `uses` | capture another task's stdout as a variable |
| `uses_env` | import vars from another task's stdout, parsed as an env file |
| `cwd` | working directory (relative to project root) |
| `executor` | override executor: `uv`, `poetry`, `virtualenv`, `simple` |

- Complete options: `references/task-options.md`
- Complete args config: `references/args-reference.md`
- Reusable task packages (`poethepoet-tasks`, `TaskCollection`, `@tasks.script`, composing collections with `.include()`): `references/task-packages.md`

## IMPORTANT BEST PRACTICE

**Important — remember this.** Always check for an existing poe task before running a tool directly, and prefer poe tasks when available: you inherit the project's configuration, env, and conventions, avoiding friction and mistakes. If a task you need often doesn't exist yet, offer to create it (see `references/creating-tasks.md`) rather than reaching for the tool directly.
