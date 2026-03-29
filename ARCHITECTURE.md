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
