# Task Options Reference

All options are available on any task type unless noted.

---

## Parameter expansion

Parameter expansion is the default across poe: task bodies (`cmd`, `ref`, `expr`) and most config options (`env` values, `cwd`, `capture_stdout`, `envfile` paths and values, arg `default` values, include paths) all support it. When you need to make something conditional on an environment variable, reach for expansion first.

| Syntax            | Meaning                                                   |
| ----------------- | --------------------------------------------------------- |
| `${VAR}`          | Value of VAR                                              |
| `${VAR:-default}` | Value of VAR, or `default` if unset/empty                 |
| `${VAR:+alt}`     | `alt` if VAR is set and non-empty, otherwise empty string |

These are especially useful for optional feature flags, environment-specific paths, and conditional arguments:

```toml
cmd = "server --port ${_port:-8080} ${_debug:+--debug}"
env.DATA_DIR = "${XDG_DATA_HOME:-${HOME}/.local/share}/myapp"
cwd = "${SUBPROJECT:-client}"
args = ["_port", "_debug"]
```

`cmd` task bodies additionally support glob expansion. Expansion in `envfile` values follows the same rules but in-file definitions take precedence over the base environment during expansion.

---

## help

Single-line description shown in `poe` listing and `poe --help <task>`. Always add this to make tasks self documenting. The focus should be on "what the task is for".

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

**Private variables** (lowercase + `_` prefix): available in task config expansion but NOT exposed to subprocesses — useful for sensitive values or just to avoid spamming the environment with unnecessary variables:

```toml
env = { _token = "${SECRET_TOKEN}" }  # use as ${_token} in cmd, invisible to shell tasks
```

**Precedence** (lowest to highest): host env → global envfile → global env → task envfile → task env → `uses_env` / `uses` outputs → task args

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

Run other tasks before this one starts.

```toml
[tool.poe.tasks.deploy]
help = "Build and deploy"
cmd = "aws s3 sync ./build s3://my-bucket"
deps = ["build-frontend", "build-backend"]
```

`deps` and `uses` task references are similar to ref tasks so they can also pass arguments to those tasks and reference environment variables or args via parameter expansions.

---

## uses

Capture the stdout of other tasks as variables available during this task.

```toml
[tool.poe.tasks._get-version]
script = "version:get()"

[tool.poe.tasks.tag]
help = "Tag the current commit with the package version"
cmd = "git tag v${_version}"
uses = { _version = "_get-version" }
```

- Key is the variable name; value is a task invocation
- Variables are available in parameter expansion (`${_version}`)
- Prefix all lowercase variables with `_` to keep the value out of the subprocess environment

---

## uses_env

Capture the stdout of other task(s) and load environment variables from it, parsing each one's output as an env file (dotenv syntax). Unlike `uses`, a single subtask can provide zero or more variables, which it names itself.

```toml
[tool.poe.tasks._aws-creds]
shell = "aws-vault exec my-profile -- env | grep '^AWS_'"

[tool.poe.tasks.deploy]
cmd = "terraform apply"
uses_env = "_aws-creds"   # or a list: uses_env = ["_aws-creds", "_other-creds"]
```

- Value is a task invocation, or a list of them (applied in order; later wins)
- Each task's stdout is parsed as an env file: `KEY=value` lines, optional leading `export`, `#` comments and blank lines ignored, `${VAR}` expanded against the current env
- Output is **not** whitespace-collapsed (unlike `uses`) — newlines separate assignments
- Loaded `_`-prefixed lowercase names stay private to the subprocess, like `uses`
- On a name collision, explicit `uses` entries take precedence over variables loaded via `uses_env`

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

- These map onto `uv run` cli options, and can be used to force tasks to run with different a venv managed by uv
- To see how the uv executor can be configured to manage task specific envs see this guide: https://poethepoet.natn.io/guides/tox_replacement_guide.html

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

Use `/dev/null` to discard output entirely.

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

Replace the poe process with the task's process (Unix only, has no effect on Windows).
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

This is useful when organizing many tasks for which a natural grouping exists.
