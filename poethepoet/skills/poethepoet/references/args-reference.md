# Args Configuration Reference

Args let users pass parameters to a task at the command line: `poe <task> --arg-name value`. This feature is functionally close to argparse in python.

## Syntax options

**Abbreviated** (array of strings — creates `--name` options with no defaults):

```toml
args = ["host", "port"]
# Usage: poe serve --host 0.0.0.0 --port 8001
```

**Inline tables** (array of dicts — add defaults, types, help):

```toml
args = [
  { name = "host", default = "localhost", help = "Host to bind" },
  { name = "port", default = "9000", type = "integer", help = "Port to listen on" }
]
```

**Array of tables** (full control):

```toml
[[tool.poe.tasks.serve.args]]
name = "host"
options = ["-h", "--host"]
default = "localhost"
help = "Host to bind"

[[tool.poe.tasks.serve.args]]
name = "port"
options = ["-p", "--port"]
default = "8000"
type = "integer"
help = "Port to listen on"
```

**Subtable form** (alternative full syntax):

```toml
[tool.poe.tasks.serve.args.host]
options = ["-h", "--host"]
default = "localhost"
help = "Host to bind"
```

---

## All arg options

| Option       | Type               | Description                                                                    |
| ------------ | ------------------ | ------------------------------------------------------------------------------ |
| `name`       | string             | Arg name — required in array form                                              |
| `options`    | list[str]          | CLI flags, e.g. `["-h", "--host"]`. Default: `["--name"]`                      |
| `default`    | str/int/float/bool | Default value; supports `${VAR}` parameter expansion including :- :+ operators |
| `help`       | string             | Help text in `poe --help <task>`                                               |
| `type`       | string             | `"string"` (default), `"integer"`, `"float"`, `"boolean"`                      |
| `positional` | bool               | Positional arg — no flag needed                                                |
| `required`   | bool               | Fail if not provided                                                           |
| `choices`    | list               | Restrict to these values (enforced)                                            |
| `multiple`   | bool or int        | Accept multiple values; int = exact count                                      |

By default the options are inferred from the name, e.g. if the name is `"level"` options will be `["--level"]` unless specified.

---

## Positional args

Positional args are provided without a flag name:

```toml
[[tool.poe.tasks.deploy.args]]
name = "environment"
positional = true
choices = ["staging", "production"]
required = true
help = "Target environment"
```

Usage: `poe deploy production`

Only one positional arg can have `multiple = true`, and it must be last.

---

## Boolean flags

Type `boolean` creates a flag that is true when present (or false if `default = true`):

```toml
args = [{ name = "verbose", options = ["-v", "--verbose"], type = "boolean" }]
```

Usage: `poe test --verbose` (true) or `poe test` (false / default)

The `default` for a boolean arg must be a TOML bool, or a case-insensitive string literal (with optional surrounding whitespace) from `"t"`/`"true"`/`"1"` (true) or `"f"`/`"false"`/`"0"`/`""` (false). Templated strings (e.g. `"${VAR}"`) are also accepted and re-checked once resolved.

In script/expr tasks the resulting pythonic variable will have type the declared type (e.g. boolean). However when accessed via parameter expansion or as an environment variable at runtime, the variable will be `"True"` if truthy, or unset of falsey, so that `:-` and `:+` parameter expansion operators work seamlessly, and for consistent semantics across interpreters in shell tasks.

---

## Multiple values

```toml
args = [{ name = "files", positional = true, multiple = true }]
```

Usage: `poe process file1.txt file2.txt`

- In `cmd` tasks: exposed as space-delimited string `${files}`
- In `script` tasks: passed as `list[str]`

For option args (flags), values can be supplied in any of three styles, freely mixed:

- Space-separated: `poe task --engines v2 v8`
- Repeated flag: `poe task --engines v2 --engines v8`
- Mixed: `poe task --engines v2 v8 --engines v10`

When `multiple = N` (an exact count), the **total** number of values across all occurrences must equal N — e.g. with `multiple = 2`, both `--widgets a b` and `--widgets a --widgets b` are valid.

---

## Private args (config-only variables)

Prefix the arg name with `_` (must be all lowercase) to prevent it from being set as an environment variable. Useful for passing values to Python scripts without leaking them to shell tasks or subprocesses.

```toml
args = [{ name = "_target", positional = true }]
```

- Available in `cmd` or `ref` parameter expansion as `${_target}` or in task options that support parameter expansions.
- Available in `script` or `expr` task call expressions as `_target`
- **NOT** set as an environment variable (shell tasks and subprocesses can't see it)
- The CLI flag uses the name without the underscore: `poe <task> --target value`

---

## How args are available by task type

| Task type              | How to access args                                                                 |
| ---------------------- | ---------------------------------------------------------------------------------- |
| `cmd`                  | `${name}` in parameter expansion                                                   |
| `shell`                | `${name}` environment variable (public args only)                                  |
| `script`               | As kwargs when no parens: `script = "module:fn"` with `args = ["x"]` → `fn(x=val)` |
| `script` (with parens) | Explicitly in call: `"module:fn(_x, y=_y)"`                                        |
| `script` (module form) | Re-emitted on the module's `sys.argv` (with defaults applied)                      |
| `expr`                 | As Python variables: `name` is directly accessible                                 |
| `sequence`/`parallel`  | Via env vars, or forwarded via `$POE_EXTRA_ARGS`                                   |

---

## Free arguments (after --)

Args passed after `--` on the command line are "free args" — not matched to any defined arg:

```bash
poe test -- -x -k "my_test"    # -x and -k "my_test" are free args
```

How they're available:

- **`cmd` tasks**: Auto-appended to the command. Use `$POE_EXTRA_ARGS` for explicit placement
- **`shell` tasks**: Available as `$POE_EXTRA_ARGS`
- **`script`/`expr` tasks**: Available as `_extra_args` (a `list[str]`)

**Forwarding to subtasks** — only subtasks that explicitly reference `$POE_EXTRA_ARGS` receive free args:

```toml
[tool.poe.tasks.check]
sequence = [
  "lint $POE_EXTRA_ARGS",   # receives free args
  "test $POE_EXTRA_ARGS",   # receives free args
  "build"                   # does NOT receive free args
]
```

The follow task types have subtacks: sequence, parallel, switch, ref

If no args are declared then all cli arguments are captured as "free args", so a task declared as simply `test.cmd = "pytest"` for example will forward any arguments passed on the CLI to pytest.

---

## Defaults from environment variables

```toml
args = [{ name = "AWS_REGION", options = ["--region", "-r"] default = "${AWS_DEFAULT_REGION:-us-east-1}" }]
```

The fact that args are normally exposed as environment variables can be useful when the task explicitly needed, for example calling an arg `"AWS_REGION"` will set that environment variable for all subprocesses of the task.

## If provided the default value will be appended in the help messages automatically.

## Constrained choices

```toml
[[tool.poe.tasks.serve.args]]
name = "flavor"
positional = true
choices = ["development", "staging", "production"]
required = true
```

Poe validates the value at runtime and shows the choices in help output.

---

## Stylistic preferences

- The `choices` arg option should be used whenever a small set of allowed options is known.
- The inline tables syntax is usually the best.
- Help text should be limited to 1 line (<80 chars) when possible.
- prefer \_private arg names for most tasks types when there is no need to access the variables from the environment at runtime. - **NEVER** use \_private arg names with shell tasks which can only access variables from the environment at runtime.
