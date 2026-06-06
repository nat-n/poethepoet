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
ls poe_tasks.toml poe_tasks.yaml poe_tasks.json 2>/dev/null
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
- **Existing `poe_tasks.toml` or `poe_tasks.yaml`** → use that file
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
| Shell pipes, loops, conditionals                                         | **`shell`**                         |
| Python logic or async                                                    | **`script`**                        |
| Run A then B                                                             | **`sequence`** (or array shorthand) |
| Run A and B simultaneously                                               | **`parallel`**                      |
| Platform-specific behavior or switching task content based on conditions | **`switch`**                        |
| Computed output                                                          | **`expr`**                          |

**When in doubt, use `cmd`.** It's portable, predictable, and the right choice for the vast majority of tasks.

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

Prefix task names with `_` to hide them from `poe` listing while keeping them usable for composition:

```toml
[tool.poe.tasks._get-bucket-name]
shell = "aws cloudformation describe-stacks | jq -r '...'"

[tool.poe.tasks.deploy]
cmd = "aws s3 sync ./build s3://${_bucket}"
uses = { _bucket = "_get-bucket-name" }
help = "Deploy to S3"
```

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

```toml
# pyproject.toml
[tool.poe]
include = "tasks/common.toml"
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
