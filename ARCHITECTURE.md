# Architecture - by Agents for Agents

## Module Overview

```
poethepoet/
├── __init__.py      # Entry point (main)
├── app.py           # PoeThePoet - orchestrates everything
├── ui.py            # CLI parsing, help, output formatting
├── context.py       # RunContext - execution state
│
├── config/          # Configuration loading
│   └── config.py    # PoeConfig - loads from pyproject.toml/poe_tasks.*
│
├── task/            # Task type implementations
│   ├── base.py      # PoeTask + metaclass registry
│   ├── cmd.py       # Shell commands
│   ├── shell.py     # Shell scripts
│   ├── script.py    # Python function calls
│   ├── expr.py      # Python expressions
│   ├── sequence.py  # Sequential composition
│   ├── graph.py     # DAG-based composition
│   └── ...
│
├── executor/        # Execution environments
│   ├── base.py      # PoeExecutor + metaclass registry
│   ├── simple.py    # Direct subprocess
│   ├── poetry.py    # Poetry virtualenv
│   └── uv.py        # uv virtualenv
│
├── env/             # Environment variable handling
│   └── task_env.py  # TaskEnv
│
├── completion/      # Shell completion scripts
│   ├── zsh.py       # Zsh completion with task descriptions + args
│   ├── bash.py      # Bash completion
│   └── fish.py      # Fish completion
│
└── helpers/         # Utilities
    └── command/     # Command-line AST parsing
```

## Execution Flow

```
CLI invocation
    │
    ▼
PoeThePoet(app.py)
    │
    ├─► PoeConfig.load() ──► Parse pyproject.toml / poe_tasks.*
    │
    ├─► PoeUi.build_parser() ──► CLI argument handling
    │
    ▼
RunContext.execute_task()
    │
    ├─► TaskSpecFactory ──► Create task instance from config
    │
    ├─► PoeTask._handle_run() ──► Task-type-specific logic
    │
    ▼
PoeExecutor.execute()
    │
    ▼
subprocess (with appropriate virtualenv)
```

## Key Abstractions

**PoeTask** (`task/base.py`)
- Base class for all task types
- Metaclass auto-registers subclasses by `__key__`
- `_handle_run()` is the main extension point

**PoeExecutor** (`executor/base.py`)
- Manages how tasks are executed (which Python, which env)
- Same metaclass pattern as tasks

**PoeConfig** (`config/config.py`)
- Async config loading from multiple file formats
- Supports includes and packaged tasks

**PoeOptions** (`options/base.py`)
- Used by PoeTask, PoeExecutor, and PoeConfig to model, parse and access configuration
- Provides some powerful abstractions to streamline safely accessing config fields

**RunContext** (`context.py`)
- Carries execution state through the task tree
- Handles output capture for composed tasks

## Variable Resolution Model

The trickiest part of Poe's runtime model is that task values flow through two related
channels:

- **Typed args**: python values stored on `TaskEnv` and consumed directly by `expr` and
  `script` tasks
- **Environment projection**: string values exposed to subprocess-oriented tasks such as
  `cmd` and `shell`

These channels are derived from the same task state, but they are observed
differently by different task types.

### Layering and precedence

Task environment state is built by layering values in roughly this order:

1. Host environment
2. Project-level `envfile`
3. Project-level `env`
4. Parent task state
5. `uses_env` outputs
6. `uses` outputs
7. Task-level `envfile`
8. Task-level `env`
9. Task args

The principle is: values closer to the running task override values further away.
`uses`/`uses_env` outputs are applied *before* the task's own `envfile` and `env`
(see `PoeTask.TaskSpec.get_task_env`) so that task `env` values can template them,
e.g. `env = { URL = "s3://${_bucket}" }`. A consequence is that a task-level `env`
value overrides a `uses`/`uses_env` value of the same name (unless declared with
`.default`). Conversely, task args are registered after the task's `env`/`envfile`
are resolved, so a task's own args cannot be referenced when templating its own
`env`/`envfile` (args of a parent task can be). Project-level `env`/`envfile` from
included configs are applied before the main config's (see `RunContext.__init__`).
Child tasks always inherit parent task state first, and then apply their own config and
argument parsing on top.

### Inheritance and shadowing

Orchestration tasks (`sequence`, `parallel`, `switch`, `ref`) do not get special-case
variable semantics. A child task always starts from inherited parent state.

If the child task declares an arg with the same name as an inherited value, then the
child task's parsed arg value wins for that name. This includes defaults: a child arg
default is treated the same as a value obtained from the child invocation. Explicit
values in a referenced task invocation (for example the content of a `ref` task) have
the highest precedence for that child task.

### Private variables

Variables whose names start with `_` and contain no uppercase characters are treated as
private when they are introduced by Poe-managed sources such as `env`, `envfile`,
`uses`, or args.

Private variables:

- remain available for config-time interpolation
- can be inherited by child tasks
- can be remapped to public variables via task-level `env`
- are filtered from the subprocess environment

Host environment variables are preserved verbatim and are not implicitly reclassified as
private.

### Boolean args

Boolean args are not special with respect to inheritance or precedence, but they do
have special environment projection semantics:

- typed value `True` projects to environment value `"True"`
- typed value `False` remains available as `False` to `expr`/`script`, but its
  environment projection is **unset**
- these boolean projections can be replaced with custom strings via the
  `true_string`/`false_string` arg options
- the same unset projection applies to an omitted arg with no default (`None`) and to
  a `multiple` arg that received no values (`[]`)

This gives consistent falsey behavior across shells and subprocesses while preserving
typed access for task types that can consume python values directly.

### Observation points by task type

Different task types observe the same underlying state in different ways:

- `cmd`: sees environment projection plus Poe's own parameter expansion
- `shell`: sees runtime environment only, interpreted by the selected shell
- `expr`: sees typed args directly, and `${...}` template expansion as strings
- `script`: sees typed args directly, `sys.argv`, and `os.environ`

When behavior looks inconsistent across task types, the first question should be:
"Is this task reading the typed arg channel or the subprocess environment channel?"

## Task types

There are two categories of task types:
- Execution tasks that run task content in a subprocess via an executor, e.g. cmd, script, shell, expr
- Orchestration tasks that run other tasks, e.g. ref, switch, sequence, parallel

## Composition Model

Tasks can be composed three ways:

1. **Sequence** - Run tasks in order, optionally ignoring failures
2. **Parallel** - Run tasks concurrently with colored output
3. **Graph** - DAG execution with dependencies (`deps` key)

Graph tasks capture stdout from dependencies, optionally making output available to downstream tasks.
