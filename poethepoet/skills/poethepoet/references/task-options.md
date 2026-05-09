# Task Options Reference

All options are available on any task type unless noted.

---

## Parameter expansion in config options

Several config options support `${VAR}` interpolation at config-load time. The bash-like `:-` and `:+` operators are also supported:

| Syntax | Meaning |
|--------|---------|
| `${VAR}` | Value of VAR |
| `${VAR:-default}` | Value of VAR, or `default` if unset/empty |
| `${VAR:+alt}` | `alt` if VAR is set and non-empty, otherwise empty |

**Options that support interpolation**: `env` values, `cwd`, `capture_stdout`, `envfile` paths, arg `default` values, and include paths.

This is distinct from parameter expansion in `cmd` task bodies, which additionally supports glob expansion.

---

## help

Single-line description shown in `poe` listing and `poe --help <task>`. Always add this.

```toml
[tool.poe.tasks.test]
cmd = "pytest"
help = "Run the test suite"
```

---

## env

Set environment variables for the task. These layer on top of global env.

```toml
[tool.poe.tasks.serve]
cmd = "uvicorn app:main"
env = { PORT = "8080", DEBUG = "1" }
```

**Default value** (only set if not already in the environment):
```toml
[tool.poe.tasks.serve.env]
PORT.default = "8080"
```

**Reference other variables**:
```toml
[tool.poe.tasks.deploy]
env.REGION = "${AWS_DEFAULT_REGION:-us-east-1}"
```

**Private variables** (lowercase + `_` prefix): available in task config expansion but NOT exposed to subprocesses — useful for sensitive values:
```toml
env = { _token = "${SECRET_TOKEN}" }  # use as ${_token} in cmd, invisible to shell tasks
```

**Precedence** (lowest to highest): host env → global envfile → global env → task envfile → task env → `uses` outputs → task args

---

## envfile

Load environment variables from files.

```toml
envfile = ".env"

# Multiple files (loaded in order):
envfile = [".env", "local.env"]

# With optional files:
[tool.poe.tasks.serve.envfile]
expected = [".env"]       # warn if missing
optional = ["local.env"]  # silently skip if missing
```

Paths are relative to the project root. Supports `${POE_ROOT}`, `${POE_GIT_DIR}` etc.

---

## deps

Run other tasks before this one starts. Deps run in parallel by default.

```toml
[tool.poe.tasks.deploy]
cmd = "aws s3 sync ./build s3://my-bucket"
deps = ["build-frontend", "build-backend"]
help = "Build and deploy"
```

---

## uses

Capture the stdout of other tasks as variables available during this task.

```toml
[tool.poe.tasks._get-version]
script = "version:get()"

[tool.poe.tasks.tag]
cmd = "git tag v${_version}"
uses = { _version = "_get-version" }
help = "Tag the current commit with the package version"
```

- Key is the variable name; value is a task invocation
- Variables are available in parameter expansion (`${_version}`)
- Prefix with `_` to keep the value out of the subprocess environment

---

## cwd

Override the working directory for the task. Relative to project root.

```toml
[tool.poe.tasks.build-client]
cmd = "npm run build"
cwd = "./client"
help = "Build the frontend"
```

Supports env var interpolation: `cwd = "${SUBPROJECT_DIR}"`.
Use `${POE_PWD}` to reference the directory poe was invoked from.

---

## executor

Override how poe runs the task's subprocess.

```toml
# Simple string:
executor = "simple"   # run without any managed venv

# With options:
executor = { type = "uv", group = "server" }
executor = { type = "virtualenv", location = ".venv-special" }
```

Valid types: `auto` (detect automatically), `poetry`, `uv`, `virtualenv`, `simple`

**uv executor options**: `extra`, `group`, `no-group`, `with`, `isolated`, `exact`, `no-sync`, `locked`, `frozen`, `no-project`, `python`

**virtualenv executor options**: `location` (path to venv; default: `.venv` or `venv`)

**Global default** (in `[tool.poe]`):
```toml
[tool.poe]
executor = "auto"   # or force: "uv", "poetry", etc.
```

---

## capture_stdout

Redirect task stdout to a file instead of the terminal.

```toml
[tool.poe.tasks.log-build]
cmd = "python --version"
capture_stdout = "build_info.txt"
```

Use `/dev/null` (or `NUL` on Windows) to discard output entirely.

---

## verbosity

Override poe's own output verbosity for this specific task (-3 to 3).

```toml
[tool.poe.tasks.credentials]
cmd = "aws secretsmanager get-secret-value"
verbosity = -1   # suppress poe's output header for this task
```

---

## ignore_fail

Allow the task to fail without aborting the parent sequence/parallel.

For `cmd`/`shell`/`script`/`expr` tasks:
```toml
ignore_fail = true       # ignore any non-zero exit code
ignore_fail = [1, 2]     # ignore specific exit codes only
```

For `sequence`/`parallel` tasks:
- `true` — continue running; return 0 if remaining tasks succeed
- `"return_zero"` — always return 0 regardless of failures
- `"return_non_zero"` — continue but propagate failure in exit code

---

## use_exec

Replace the poe process with the task's process (Unix only, not available on Windows).
The task cannot be referenced by other tasks or use `deps`.

```toml
[tool.poe.tasks.serve]
cmd = "gunicorn app:main"
use_exec = true   # gunicorn becomes the process, not a subprocess of poe
```

---

## Global configuration options

Set these under `[tool.poe]` to apply project-wide defaults:

```toml
[tool.poe]
verbosity = 0                           # -1 quiet, 0 normal, 1 verbose
default_task_type = "cmd"               # type for string task definitions
default_array_task_type = "sequence"    # type for array task definitions
default_array_item_task_type = "ref"    # type for items in task arrays
shell_interpreter = "bash"              # default shell for shell tasks
executor = "auto"                       # executor for all tasks

[tool.poe.env]
PYTHONPATH = "src"
STAGE = "dev"

[tool.poe.envfile]
expected = [".env"]
optional = ["local.env"]
```

## Task groups

Group related tasks under a named heading in `poe` output:

```toml
[tool.poe.groups.dev]
heading = "Development"

[tool.poe.groups.dev.tasks.serve]
cmd = "uvicorn app:main --reload"
help = "Run dev server"

[tool.poe.groups.dev.tasks.shell]
cmd = "python manage.py shell"
help = "Open a Django shell"

[tool.poe.groups.qa]
heading = "Quality Assurance"
executor = { type = "uv", group = "dev" }   # shared executor for the group

[tool.poe.groups.qa.tasks.test]
cmd = "pytest"
help = "Run tests"
```

## Include tasks from other files

Split large task configs across files:

```toml
[tool.poe]
include = "shared_tasks.toml"

# Multiple includes:
include = ["common/tasks.toml", "generated.json"]

# With options:
[[tool.poe.include]]
path = "subproject/pyproject.toml"
cwd = "subproject"      # tasks from this file run in this directory
recursive = false       # don't follow includes within the included file
```

Included `.toml`/`.yaml`/`.json` files don't require the `tool.poe` namespace.

## Include tasks from Python functions

```toml
[tool.poe]
include_script = "mypkg:get_tasks"
# or with args:
include_script = "mypkg:get_tasks(prefix='myprefix-')"
```

The function receives no args and returns `{"tasks": {...}}` (optionally also `"env"` and `"envfile"` keys).
