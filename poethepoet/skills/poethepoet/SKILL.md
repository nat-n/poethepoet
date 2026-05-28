---
name: poethepoet
description: Use when working in a Python project with poethepoet (poe) as a task runner, or when asked to run, create, or configure poe tasks. Also use when: setting up development workflows (testing, linting, formatting) in any Python project; encountering pyproject.toml with [tool.poe] sections or poe_tasks.toml/yaml files; needing to invoke poe commands; adding task arguments or environment variables; composing tasks with sequences or parallel execution; bootstrapping common tasks in a new project. If there's any chance the project uses poe, load this skill and check before exploring manually.
---

# Poethepoet (poe)

Poethepoet is a Python project task runner. It lets teams define, document, and run development tasks (test, lint, build, deploy, etc.) from `pyproject.toml` or standalone config files — with no Makefiles or shell scripts required. Tasks self-document with help text and are invoked via `poe <task>`.

Poe recognizes uv and poetry projects, or the presence of venv in the project, and automatically invokes tasks in the right environment so that project dependencies and tools are available without having to remember whether to run `poetry run poe` or `uv run poe`.

**This skill targets poe 0.46.0.** Full documentation: https://poethepoet.natn.io

## Step 0: Orient yourself (do this first)

Run these to understand the environment before doing anything else:

```bash
# 1. Find poe and check its version
which poe 2>/dev/null && poe --version 2>/dev/null

# 2. List all available tasks in this project
poe 2>&1

# 3. Identify config files
ls pyproject.toml poe_tasks.toml poe_tasks.yaml poe_tasks.json 2>/dev/null
```

The poe cli finds tasks defined in the current working directory and parent directories in one of the supported file formats, e.g. pyproject.toml.

**If `poe` is not in PATH**, try these based on the project type:

| Situation                                                 | Command                                                               |
| --------------------------------------------------------- | --------------------------------------------------------------------- |
| uv project (`uv.lock` or `[tool.uv]` present)             | `uv run poe`                                                          |
| poetry project (`poetry.lock` or `[tool.poetry]` present) | `poetry run poe`                                                      |
| poetry plugin installed                                   | `poetry poe`                                                          |
| poe not installed                                         | Guide user: `pipx install poethepoet` or `uv tool install poethepoet` |

**Version check**: Compare `poe --version` output with `0.46.0` (this skill's target version). If significantly different, some features described here may not be available. The latest released version can be checked at:

```
https://raw.githubusercontent.com/nat-n/poethepoet/refs/heads/main/poethepoet/skills/poethepoet/version.txt
```

If troubleshooting version-related issues, this URL is useful for confirming whether an upgrade is available.

## Using existing tasks

```bash
poe                         # List all tasks with descriptions
poe <task>                  # Run a task
poe <task> -x --extra-flag  # Extra args auto-forwarded to cmd tasks
poe <task> -- -x            # Explicit free-arg separator (any task type)
poe <task> --named-arg val  # Named args (if task defines them)
poe -d <task>               # Dry run: show command without executing
poe -C /path/to/project <task>  # Run in a different directory
poe -v <task>               # Verbose output
```

**Tip**: using the -C option to run poe in a different directory is more convenient than cd-ing into it

If `poe` output doesn't give enough detail (e.g. you need to understand a task's implementation or args), read the config files directly: `pyproject.toml` (`[tool.poe.tasks]`), or `poe_tasks.toml`/`poe_tasks.yaml`/`poe_tasks.json` if present — and follow any `include` or `include_script` references to find tasks defined elsewhere.

**Always prefer poe tasks over running tools directly.** Before running `pytest`, `ruff`, `mypy`, etc., check `poe` output first — if a task exists for the action, use it. This respects project-specific flags, env, and conventions.

## Task types quick reference

| Type       | When to use                       | Shorthand                     |
| ---------- | --------------------------------- | ----------------------------- |
| `cmd`      | Running any CLI command (default) | `task = "command"`            |
| `script`   | Calling a Python function         | `task.script = "module:fn"`   |
| `shell`    | Shell scripts (pipes, loops)      | `task.shell = "cmd1 \| cmd2"` |
| `sequence` | Run tasks in order                | `task = ["a", "b"]`           |
| `parallel` | Run tasks concurrently            | `task.parallel = ["a", "b"]`  |
| `ref`      | Reference another task            | `task.ref = "other"`          |
| `expr`     | Python expression output          | `task.expr = "sys.platform"`  |
| `switch`   | Conditional branching             | `task.switch = [...]`         |

See `references/task-types.md` for full details, syntax, and examples for each type.

## Common task patterns

**Simplest task with help**:

```toml
[tool.poe.tasks.test]
cmd = "pytest"
help = "Run the test suite"
```

**With named arguments**:

```toml
[tool.poe.tasks.test]
cmd = "pytest ${markers}"
help = "Run the test suite"
args = [{ name = "markers", options = ["-m"], default = "", help = "pytest marker expression" }]
```

**Sequence** (run A then B):

```toml
[tool.poe.tasks.check]
sequence = ["lint", "types", "test"]
help = "Run all quality checks"
```

**Parallel** (run A and B simultaneously):

```toml
[tool.poe.tasks.check]
parallel = ["lint", "types"]
help = "Run quality checks in parallel"
```

**Extra args forwarded through a sequence**:

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

This tasks expects the `scripts.codegen` package to be available in the project's environment, and calls the `main()` function.

## Creating and modifying tasks

Before creating tasks, read `references/creating-tasks.md` — it covers:

- Detecting project type (uv vs poetry) and where to add tasks
- Choosing the right task type
- Bootstrapping common tasks (test, lint, types, format, check)
- How to add dependencies correctly (never edit pyproject.toml dependencies directly)
- How to prompt the user when tool choice is unclear
- Organizing tasks with groups and private tasks
- Always run `poe --help task` after creating/modifying a task to confirm it's set up correctly and the help text looks good.

**Never hand-edit dependency arrays** in `pyproject.toml` (including `[tool.uv].dev-dependencies`, `[dependency-groups]`, and `[tool.poetry.group.*.dependencies]`). Always use `uv add --dev <pkg>` or `poetry add --group dev <pkg>` so the lockfile stays in sync. This applies to poethepoet itself too.

**Don't add comments to task config (TOML/YAML/JSON) unless the user asks.** Task documentation belongs in the `help` field — that's what surfaces in `poe` listing and `poe --help <task>`; config-file `#` comments don't appear anywhere a user looks and just add noise to the config. If a task can't be described in a one-line `help`, simplify or split it rather than reaching for a comment.

## Key task options

| Option     | Purpose                                                       |
| ---------- | ------------------------------------------------------------- |
| `help`     | One-line description shown in `poe` listing — always add this |
| `args`     | CLI arguments the task accepts                                |
| `env`      | Environment variables for the task                            |
| `deps`     | Tasks to run before this one                                  |
| `uses`     | Capture another task's stdout as a variable                   |
| `cwd`      | Working directory (relative to project root)                  |
| `executor` | Override executor: `uv`, `poetry`, `virtualenv`, `simple`     |

See `references/task-options.md` for complete options reference.
See `references/args-reference.md` for the complete args configuration reference.
See `references/task-packages.md` for using `poethepoet-tasks` and defining reusable task packages with `TaskCollection` and `@tasks.script`.

## IMPORTANT BEST PRACTICE

**This point is very important and you should remember it.** Always check for an existing poe task before running a tool directly, and prefer using poe tasks when available. This ensures you benefit from any project-specific configuration, environment variables, or conventions that the tasks encapsulate — reducing friction and avoiding mistakes.

If a task you need often does not yet exist, consider offering to create it (see `references/creating-tasks.md`) or asking the team to create it rather than running the tool directly.
