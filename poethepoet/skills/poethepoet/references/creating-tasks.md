# Creating and Bootstrapping Tasks

## Step 1: Understand the project setup

Before creating tasks, check the project type and existing config:

```bash
# Identify project type
grep -E "^\[tool\.(poetry|uv|poe)\]" pyproject.toml 2>/dev/null | head -5
ls poetry.lock uv.lock 2>/dev/null

# Check for existing poe config
grep -c "tool.poe" pyproject.toml 2>/dev/null

# Check for standalone task files
ls poe_tasks.toml poe_tasks.yaml poe_tasks.yml poe_tasks.json 2>/dev/null
```

**Project type determines the poe command and how to add dependencies:**

| Project type                              | poe command                   | Add dev dependency             |
| ----------------------------------------- | ----------------------------- | ------------------------------ |
| uv (`uv.lock` or `[tool.uv]`)             | `uv run poe`                  | `uv add --dev <pkg>`           |
| poetry (`poetry.lock` or `[tool.poetry]`) | `poetry run poe`              | `poetry add --group dev <pkg>` |
| standalone (neither)                      | `poe` (if globally installed) | User decides                   |

---

## Step 2: Choose where to put tasks

- **Existing project with `[tool.poe]` in pyproject.toml** → add to `pyproject.toml`
- **Existing `poe_tasks.toml` or `poe_tasks.yaml`/`.yml`** → use that file
- **New project with no poe config** → add `[tool.poe.tasks]` to `pyproject.toml`
- **Complex task sets warranting separation** → create `poe_tasks.toml` (exclude from `[tool.poe]` in pyproject.toml)

For standalone task files, you don't need the `[tool.poe]` namespace:

```toml
# poe_tasks.toml
[tasks.test]
cmd = "pytest"
help = "Run the test suite"
```

---

## Step 3: Choose the task type

Use `cmd` by default. Only reach for other types when you genuinely need their features:

| Need                                                                     | Use                                 |
| ------------------------------------------------------------------------ | ----------------------------------- |
| Run a CLI command                                                        | **`cmd`** (default)                 |
| Shell scripting: pipes, redirects, loops, tests on runtime state         | **`shell`**                         |
| Python logic or async                                                    | **`script`**                        |
| Run A then B                                                             | **`sequence`** (or array shorthand) |
| Run A and B simultaneously                                               | **`parallel`**                      |
| Different steps depending on an arg, env var, or platform                | **`switch`**                        |
| Computed output                                                          | **`expr`**                          |

**When in doubt, use `cmd`.** It's portable, predictable, and the right choice for the vast majority of tasks.

### Declare it in poe before scripting it in bash

Bash is the familiar tool, so it is tempting to write a `shell` task whenever a task needs a fallback, a branch, or a computed value. Poe has a declarative feature for most of these, and it is usually the better fit: it shows up in `poe --help <task>` and `poe -d`, is validated before anything runs, and stays portable.

| If you are about to write this in bash…                    | …use this instead                                                         |
| ---------------------------------------------------------- | ------------------------------------------------------------------------- |
| `REGION="${REGION:-eu-west-1}"`, `if [ -z "$X" ]; then X=…` | arg `default = "eu-west-1"`, or `default = "${SOME_ENV_VAR:-eu-west-1}"`   |
| `if [ -z "$X" ]; then echo "X is required"; exit 1; fi`     | arg `required = true`                                                     |
| `case "$X" in a\|b) ;; *) exit 1 ;; esac` to validate       | arg `choices = ["a", "b"]`                                                |
| `case "$TARGET" in app) … ;; *) … ;; esac` to pick steps     | `switch` with `control.expr = "TARGET"`; a case can be a `sequence`       |
| `[ -n "$TAG" ] && ARGS="--tag $TAG"`                        | `${TAG:+--tag ${TAG}}` in the `cmd`                                       |
| `NAME="$(some-command)"`                                    | `uses = { _name = "_some-task" }`                                         |
| `eval "$(creds-command)"`, `source .env`                    | `uses_env = "_creds-task"`, `envfile = ".env"`                            |
| `step-one && step-two`                                      | `sequence = ["step-one", "step-two"]`                                     |
| `check-login \|\| exit 1` before the real work               | `deps = ["_check-login"]`                                                 |
| `cd subdir && …`                                            | `cwd = "subdir"`                                                          |
| `export X=…`                                                | `env.X = "…"`                                                             |
| `a & b & wait`                                              | `parallel = ["a", "b"]`                                                   |
| `… \|\| true`                                                | `ignore_fail = true`                                                      |

`shell` tasks are still the right tool when the work is genuinely a shell script: pipes, redirects, loops, tests on state that only exists at run time, or a longer script that would be awkward to break into poe features. The point is to check this table first, not to avoid `shell`.

---

## Step 4: Always add help text

Every task visible to users should have a `help` line — it's what makes `poe` self-documenting:

```toml
[tool.poe.tasks.test]
help = "Run the test suite"     # shown in `poe` output
cmd = "pytest"
```

Keep help text to a single, clear line. It appears in `poe` listing and `poe --help <task>`.

**Don't add `#` comments around or inside task definitions** (TOML, YAML, or JSON) unless the user asks or some detail about how the task works really needs explanation to avoid problematic confusion. `help` is the canonical place for task documentation (though it should usually just describe the purpose of the task) — it surfaces to users; config-file comments don't. If a task seems to need a comment to explain what it does, that's usually a signal to rename it, refine its `help`, or split it.

---

## Bootstrapping common tasks

When setting up a new project, **ask the user** before choosing tools if you're not sure from context. Common choices:

### Testing

Almost always `pytest`. Ask only if the project already has another framework set up.

```toml
[tool.poe.tasks.test]
cmd = "pytest"
help = "Run the test suite"
```

With coverage:

```toml
[tool.poe.tasks.test]
cmd = "pytest --cov=src --cov-report=term-missing"
help = "Run the test suite with coverage"
```

Extra args (like `-x`, `-k`, `-v`) are auto-forwarded to `cmd` tasks:

```bash
poe test -x -k "my_feature"   # works automatically
```

### Linting

**Prefer `ruff`** — it's fast and covers linting + formatting in one tool. Ask if the project already uses something else.

```toml
[tool.poe.tasks.lint]
cmd = "ruff check ."
help = "Run linter"
```

With auto-fix support:

```toml
[tool.poe.tasks.lint]
cmd = "ruff check . $POE_EXTRA_ARGS"
help = "Run linter (pass --fix to auto-fix)"
```

### Type checking

**Ask the user**: `mypy` (most established, widely supported) or `ty` (newer, faster, from Astral — same team as ruff). Check what's already in the project deps.

```toml
# mypy:
[tool.poe.tasks.types]
cmd = "mypy ."
help = "Run type checker"

# ty:
[tool.poe.tasks.types]
cmd = "ty check"
help = "Run type checker"
```

### Formatting

**Prefer `ruff format`** if ruff is already in use.

```toml
# ruff format:
[tool.poe.tasks.format]
cmd = "ruff format ."
help = "Auto-format code"
```

### Combined quality check

Similar checks can be run in **parallel** (faster):

```toml
[tool.poe.tasks.check]
parallel = ["lint", "types", "test"]
help = "Run all quality checks"
```

Sequential takes longer but gives clearer output:

```toml
[tool.poe.tasks.check]
sequence = ["lint", "types", "test"]
help = "Run all quality checks"
```

### Typical full setup

```toml
[tool.poe.tasks.test]
cmd = "pytest"
help = "Run the test suite"

[tool.poe.tasks.lint]
cmd = "ruff check ."
help = "Lint the codebase"

[tool.poe.tasks.types]
cmd = "mypy ."
help = "Run type checker"

[tool.poe.tasks.format]
cmd = "ruff format ."
help = "Auto-format code"

[tool.poe.tasks.check]
sequence = ["lint", "types", "test"]
help = "Run all quality checks"
```

---

## Adding dependencies

**Never hand-edit dependency arrays in `pyproject.toml`.** This applies to _all_ dependency tables, including:

- `[project.dependencies]` and `[project.optional-dependencies]`
- `[tool.uv].dev-dependencies` and `[dependency-groups]`
- `[tool.poetry.dependencies]` and `[tool.poetry.group.*.dependencies]`

Always go through the project's package manager so the lockfile updates and version pinning stays consistent — and ask the user before adding packages they haven't requested.

```bash
# uv project:
uv add --dev ruff mypy pytest pytest-cov

# poetry project:
poetry add --group dev ruff mypy pytest pytest-cov
```

This also applies when adding poe itself: `uv add --dev poethepoet` or `poetry add --group dev poethepoet`, never by appending to a dependency array.

---

## Python scripts in the repo

For tasks that need real Python logic, use `script` type pointing to a Python function. This is one of the most powerful patterns in poethepoet.

> **Tip:** If you're defining multiple script tasks, consider using a `TaskCollection` with the `@tasks.script` decorator — it infers args from the function signature automatically, eliminating the TOML `args` block. See `references/task-packages.md`.

### Exposing a Python function's parameters on the CLI

When a Python function has typed parameters, you can expose them directly as CLI arguments. Poe passes the args to the function in the order they appear in the call expression.

```python
# scripts/process.py
def main(
    input_file: str,
    output_dir: str = "reports",
    verbose: bool = False,
    format: str = "html",
) -> None:
    """Process a data file and write a report."""
    ...
```

```toml
[tool.poe.tasks.process]
script  = "process:main(_input_file, _output_dir, _verbose, _format)"
help    = "Process a data file and write a report"
env.PYTHONPATH = "${POE_ROOT}/scripts"  # makes process.py importable

[[tool.poe.tasks.process.args]]
name       = "_input_file"
positional = true
help       = "Path to the input data file"

[[tool.poe.tasks.process.args]]
name    = "_output_dir"
options = ["-o", "--output-dir"]
default = "reports"
help    = "Directory to write the report to"

[[tool.poe.tasks.process.args]]
name    = "_verbose"
options = ["-v", "--verbose"]
type    = "boolean"
help    = "Enable verbose logging"

[[tool.poe.tasks.process.args]]
name    = "_format"
options = ["--format"]
default = "html"
help    = "Output format (html, csv, json)"
```

Now users get a fully documented CLI:

```bash
poe process data.csv                          # defaults
poe process data.csv --output-dir results -v  # with options
poe process --help                            # auto-generated help
```

Key points:

- Arg names use `_` prefix (private) — private args are **not** set as environment variables, so their values don't leak to subprocesses or shell tasks. The CLI flags drop the underscore: `--output-dir`, `--verbose`
- The explicit call expression `main(_input_file, _output_dir, _verbose, _format)` is required because the `_`-prefixed poe arg names don't match the Python parameter names; passing positionally bridges this gap
- `env.PYTHONPATH = "${POE_ROOT}/scripts"` adds `scripts/` to the path so `process` is importable directly. Alternatively, use `"${POE_ROOT}"` and reference as `scripts.process:main` — this requires `scripts/__init__.py`

### Simple script task (no args)

```toml
[tool.poe.tasks.codegen]
script = "scripts.generate:main"
help = "Run code generation"
```

```python
# scripts/generate.py
def main():
    ...
```

Advantages over `shell`:

- Proper Python error handling and type annotations
- Async support via `asyncio.run()`
- Testable
- Cross-platform by default

Make the module importable by ensuring `scripts/__init__.py` exists or configuring `PYTHONPATH`.

---

## Private tasks

Prefix a task name with `_` to make it **composition-only**: it's hidden from the `poe` listing **and cannot be run directly** (`poe _get-bucket-name` errors with "Tasks prefixed with `_` cannot be executed directly"). It exists purely to be referenced by other tasks via `deps`, `uses`, `ref`, or a sequence/parallel.

```toml
[tool.poe.tasks._get-bucket-name]
shell = "aws cloudformation describe-stacks | jq -r '...'"

[tool.poe.tasks.deploy]
cmd = "aws s3 sync ./build s3://${_bucket}"
uses = { _bucket = "_get-bucket-name" }
help = "Deploy to S3"
```

The `_` prefix is the same "internal, not public" convention used by [private args](args-reference.md) (kept out of the environment) and private env/`uses` vars (not exported to subprocesses).

---

## Compose tasks; don't call poe recursively

When a task needs to run another task, compose them with `deps`, `uses`, `ref`, or a `sequence`/`parallel` block. **Don't** invoke poe from inside a task body:

```toml
# ❌ Don't: shell out to a second poe process
[tool.poe.tasks.release]
shell = "poe test && poe build"

# ✅ Do: let poe orchestrate
[tool.poe.tasks.release]
sequence = ["test", "build"]
help = "Test then build"
```

Invoking poe from inside a task body starts a fresh poe process that re-reads config and re-resolves the executor/venv, and the dependency is invisible to poe's own graph — so you lose dependency dedup, ordering guarantees, dry-run visibility (`poe -d`), and completion. It also can't reach a private `_`-task at all, since those refuse direct invocation.

---

## Keep the task set clean

The finished task set is something a teammate reads to understand the project's workflow, so curate it:

- **Remove scaffolding.** If you created throwaway tasks to experiment or debug while building the real ones, delete them before you finish.
- **Every task should pull its weight.** Prefer a small set of clearly-purposed tasks over many tiny, overlapping, or one-off ones. If two tasks do nearly the same thing, merge or parameterize them with `args`.
- **Make the organizing principle legible.** A newcomer skimming `poe` should be able to tell why each task exists and how they group together (use `help` text and, when the list is long, `groups`).

---

## Organizing large task sets

Use groups when the task list is long enough that categorization helps:

```toml
[tool.poe.groups.dev]
heading = "Development"

[tool.poe.groups.dev.tasks.serve]
cmd = "uvicorn app:main --reload"
help = "Run development server"

[tool.poe.groups.dev.tasks.shell]
cmd = "python -c 'import app; app.shell()'"
help = "Open an interactive shell"

[tool.poe.groups.qa]
heading = "Quality Assurance"

[tool.poe.groups.qa.tasks.test]
cmd = "pytest"
help = "Run tests"

[tool.poe.groups.qa.tasks.lint]
cmd = "ruff check ."
help = "Lint"
```

Tasks without a group appear first under an implicit heading.

---

## Splitting config with includes

For large projects with many tasks, you can organize tasks across multiple files and include them. This is useful in monorepo contexts to reuse tasks across multiple python .projects.

The `include` key takes either a single path or a list of paths:

```toml
# pyproject.toml — single file
[tool.poe]
include = "tasks/common.toml"
```

```toml
# pyproject.toml — multiple files
[tool.poe]
include = ["tasks/backend.toml", "tasks/frontend.toml"]
```

```toml
# tasks/common.toml  (no [tool.poe] namespace needed)
[tasks.format]
cmd = "ruff format ."
help = "Format all code"
```

Use the `cwd` option when including a subproject's tasks:

```toml
[[tool.poe.include]]
path = "frontend/pyproject.toml"
cwd = "frontend"
```
