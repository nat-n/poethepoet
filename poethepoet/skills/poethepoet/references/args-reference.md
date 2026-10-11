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
| `options`    | list[str]          | CLI flags (non-empty), e.g. `["-h", "--host"]`. Default: `["--name"]`          |
| `default`    | str/int/float/bool | Default value; supports `${VAR}` parameter expansion including :- :+ operators. Converted to the arg's `type`, and must be valid for `type` and `choices` (config error otherwise) |
| `help`       | string             | Help text in `poe --help <task>`                                               |
| `type`       | string             | `"string"` (default), `"integer"`, `"float"`, `"boolean"`                      |
| `true_string` / `false_string` | string | Boolean args only (poe 0.49.0+): literal string for the true / false value in expansion and the environment |
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

Only one positional arg can have `multiple = true`, and it must be last. Positional args can't be `type = "boolean"`.

---

## Boolean flags

Type `boolean` creates a flag that is true when present (or false if `default = true`):

```toml
args = [{ name = "verbose", options = ["-v", "--verbose"], type = "boolean" }]
```

Usage: `poe test --verbose` (true) or `poe test` (false / default)

The `default` for a boolean arg must be a TOML bool, or a case-insensitive string literal (with optional surrounding whitespace) from `"t"`/`"true"`/`"1"` (true) or `"f"`/`"false"`/`"0"`/`""` (false). Templated strings (e.g. `"${VAR}"`) are also accepted and re-checked once resolved.

In script/expr tasks the resulting Python variable keeps its declared type. By default a boolean is exposed to parameter expansion and the subprocess environment as `"True"` when true, or unset when false.

Set `true_string` and/or `false_string` (poe 0.49.0+) to customize those environment strings. Values are literal: `${...}` is not interpolated. An explicit `""` sets an empty variable; omitting `false_string` keeps false unset. The options select by boolean value, independently of `default`, and do not change typed Python arguments or module script flag forwarding.

```toml
[tool.poe.tasks.greet]
cmd = 'echo "${hello}"'
args = [{ name = "hello", type = "boolean", true_string = "hello!", false_string = "hi!" }]
```

Use `${hello}` directly to select the configured string. `:+` and `:-` test the resulting string: a nonempty `false_string` activates `:+` even when the boolean is false, and an empty `true_string` activates `:-` even when it is true.

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

A `multiple` arg always resolves to a list. When omitted it resolves to `[]`, or to `[default]` if a `default` is set. Supplying values replaces the default rather than extending it.

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

## Free arguments

"Free args" are CLI arguments not matched to any declared arg:

- **Task without `args`**: every argument after the task name is a free arg, so `poe test -x -k "my_test"` just works. Don't add `--`: it is forwarded literally (`pytest -- -x`).
- **Task with `args`**: unknown arguments are an error; put free args after `--`: `poe test -m slow -- -x`.

How they're available:

- **`cmd` tasks**: Auto-appended to the command. Use `$POE_EXTRA_ARGS` for explicit placement
- **`shell` tasks**: Only via `$POE_EXTRA_ARGS`; if the script doesn't reference it, free args are silently dropped. It is a shell-quoted string, so plain `$POE_EXTRA_ARGS` is only safe for simple args; use `eval "pytest $POE_EXTRA_ARGS"` to keep args with spaces or quotes intact
- **`script`/`expr` tasks**: Available as `_extra_args` (a `list[str]`, empty if there are none)
- **`ref` tasks**: Auto-appended to the referenced task's invocation

**Forwarding to subtasks** — a sequence/parallel item receives free args when it passes `$POE_EXTRA_ARGS` (subtasks inherit the variable, so a subtask whose own definition references `$POE_EXTRA_ARGS` also sees them):

```toml
[tool.poe.tasks.check]
sequence = [
  "lint $POE_EXTRA_ARGS",   # receives free args
  "test $POE_EXTRA_ARGS",   # receives free args
  "build"                   # does NOT receive free args
]
```


---

## Defaults from environment variables

```toml
args = [{ name = "AWS_REGION", options = ["--region", "-r"], default = "${AWS_DEFAULT_REGION:-us-east-1}" }]
```

Because public args are exposed as environment variables, an arg named `"AWS_REGION"` sets that variable for all subprocesses of the task.

**Pitfall**: an arg that isn't passed and has no default **removes** the variable of the same name from the task's environment, even if the host or the task's `env` set it. To fall back to the inherited value, use it as the default: `default = "${AWS_REGION}"`.

If provided, the default value is appended to the help message automatically.

---

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
