# Task Packages

Task packages let you define and share poe tasks as Python code, loaded via `include_script`. This is useful for reusing tasks across projects, or for defining tasks with complex logic that doesn't fit cleanly in TOML.

This is a very powerful feature, because it means tasks can be generated dynamically with logic in python, and distributed for reuse as python packages.

[`poethepoet-tasks`](https://github.com/nat-n/poethepoet-tasks) is a python library that provides the TaskCollection abstraction for declaring and organizing poe tasks in python, as well as a ready-made collection of tasks (test, lint, format, types, check) maintained by the poe author.

See [the packaged tasks guide](https://poethepoet.natn.io/guides/packaged_tasks.html) if you need a more in depth explanation.

---

## Using poethepoet-tasks

The quickest way to bootstrap a standard dev workflow.

**Install:**

```bash
uv add --dev poethepoet-tasks   # or: poetry add --group dev poethepoet-tasks
```

**Enable all tasks:**

```toml
[tool.poe]
include_script = "poethepoet_tasks:tasks"
```

**Filter by tag** (exclusion takes precedence over inclusion):

```toml
# Only ruff formatting, no black:
include_script = "poethepoet_tasks.tasks:tasks(exclude_tags=['black'])"

# Only the test task (plus a generated `check` that runs just it):
include_script = "poethepoet_tasks.tasks:tasks(include_tags=['task-test'])"
```

`include_script` also takes a list, or tables with `script`, `cwd` and `executor` keys (`[[tool.poe.include_script]]`). It only works in the main config file; it is ignored in files loaded via `include`.

**Override tool config via env:**

```toml
[tool.poe]
env = { RUFF_CONFIG = "path/to/ruff.toml" }
include_script = "poethepoet_tasks:tasks"
```

Pin to a specific version — available tasks can change between releases.

You can see example how the provided tasks are defined [here](https://raw.githubusercontent.com/nat-n/poethepoet-tasks/refs/heads/main/src/poethepoet_tasks/tasks.py) which is also a good example of how to use TaskCollection.

**Tip**: include_script just loads the referenced python function from the project environment and executed it, expecting to get back a JSON structure matching how tasks are usually defined. You can do the same if necessary to debug generated tasks.

---

## Defining your own task package

Create a `TaskCollection` in a Python file, then point `include_script` at it.

**tasks.py** (project root, or `src/mypkg/tasks.py`):

```python
from poethepoet_tasks import TaskCollection

tasks = TaskCollection()

tasks.add(
    task_name="build",
    task_config={
        "help": "Build the project",
        "cmd": "python -m build",
    },
    tags=["build"],
)
```

**pyproject.toml:**

```toml
[tool.poe]
include_script = "tasks:tasks()"
```

All tasks are automatically tagged `task-<taskname>`, allowing consumers to include/exclude them by name.

---

## @tasks.script — inline script tasks with auto-inferred args

The most powerful pattern: decorate a Python function and poe derives the full CLI arg spec from the signature automatically. This avoids writing `args` blocks in TOML entirely.

```python
from poethepoet_tasks import TaskCollection

tasks = TaskCollection()

@tasks.script(tags=["example"])
def greet(
    name: str,          # positional (before *)
    *,                  # everything after * becomes a --option
    count: int = 1,
    shout: bool = False,
):
    """
    Greet someone.

    Args:
        name: the name to greet
        count: how many times to greet
        shout: uppercase the output
    """
    for _ in range(count):
        msg = f"Hello, {name}!"
        print(msg.upper() if shout else msg)
```

What poe infers automatically:

- **Positional vs option**: if the signature has a `*`, parameters before it become positional args and those after it `--option` flags; without a `*`, every parameter becomes a `--option` flag
- **Type**: `str`, `int`, `float`, `bool` → correct arg type (bool → flag)
- **Required vs optional**: no default → required; default provided → optional
- **Help text**: parsed from the docstring (rst or google format)
- **Task name**: function name converted to kebab-case (`greet-someone` for `greet_someone`)

Override any inferred value via decorator kwargs:

```python
@tasks.script(task_name="hi", help="Say hello", tags=["greet"])
def greet(...):
    ...
```

Set `task_args=False` to disable auto-inference and configure args manually via `options`.

---

## @tasks.generate — lazy task generation

For tasks whose existence depends on which tags are requested. A generator yields `(task_name, task_config)` tuples.

```python
@tasks.generate
def generate_check(requested_tags):
    steps = []
    if not requested_tags.excluded("task-lint"):
        steps.append("lint")
    if not requested_tags.excluded("task-types"):
        steps.append("types")
    if not requested_tags.excluded("task-test"):
        steps.append("test")
    if steps:
        yield "check", {"help": "Run all checks", "sequence": steps}
```

Useful for composite tasks (like `check`) that should automatically drop excluded subtasks.

---

## Composing collections with `.include()`

`TaskCollection.include(other)` merges another collection into this one and returns `self`, so calls chain. Use it to build on a third-party collection **and** to combine several of your own into one.

**There are two ways to combine collections — choose by the flexibility you need:**

- **Multiple `include_script` (or `include`) entries** keep each source independent and configured *in TOML at the consumer*: each entry can carry its own tag filter and args (via the function-ref string), `cwd`, or `executor`. This is the more flexible, declarative option — natural when the sources are independent (different packages/teams) or a monorepo subproject needs its own working directory. The cost: poe spawns a separate Python subprocess per entry, on every invocation including tab completion (noticeable, especially under poetry).

- **Python `.include()` into one collection** merges everything behind a single entry point and a single subprocess. Reach for it when you control the collections and want them merged uniformly, or when startup cost matters — accepting that per-entry TOML knobs (tags, args, `cwd`, `executor`) are no longer available unless you re-express them in code.

The composed form:

```python
# src/my_tasks/__init__.py
from poethepoet_tasks import TaskCollection
from . import backend_tasks, frontend_tasks  # each module exposes a TaskCollection

tasks = (
    TaskCollection()
    .include(backend_tasks.tasks)
    .include(frontend_tasks.tasks)
)
```

```toml
[tool.poe]
include_script = "my_tasks:tasks"  # one subprocess, not several
```

**Precedence is first-registered-wins, per task name**, and statically added tasks beat generated ones (`@tasks.generate`). A task already in the collection outranks one added later by `.include()` (or a later `add`) — `include()` appends the other's tasks below what's already there. So to override a task from an included collection, register your version *first*:

```python
from poethepoet_tasks import TaskCollection
from poethepoet_tasks.tasks import tasks as base_tasks  # the TaskCollection, not the function

tasks = TaskCollection()
tasks.add(
    task_name="check",
    task_config={"help": "Lint and types only", "sequence": ["lint", "types"]},
    tags=["lint", "types"],
)
tasks.include(base_tasks)  # base `check` is shadowed by ours
```

`.include()` also merges `env` (existing keys win on conflict), `envfile` (appended, de-duplicated), and any task generators.

---

## Environment variables for a task package

Set env vars (and optionally envfile) on the collection itself — they're included alongside the tasks:

```python
tasks = TaskCollection(
    env={"HOST": "127.0.0.1", "PORT": "8000"},
    envfile=[".env"],
)
tasks.env["PORT"] = "9000"
tasks.envfile.append(".secrets")
```

---

## Stylistic preferences

- If the project root has a `src` directory where python packages are defined, then you can add a `tasks/__init__.py` package there and expect poe to find it if referenced like `include_script = "tasks:tasks"`.
