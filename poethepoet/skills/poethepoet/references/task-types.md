# Task Types Reference

## cmd — Shell Command (Default)

Runs a command as a subprocess without a shell. Supports `${VAR}` parameter expansion and glob patterns.

Use when: running any CLI tool. This is the right default for most tasks.

```toml
[tool.poe.tasks]
test = "pytest --cov=src"                       # string shorthand — defaults to cmd
lint = { cmd = "ruff check .", help = "Lint" }  # inline table form

[tool.poe.tasks.build]
cmd = "poetry build"
help = "Build distribution packages"
```

**Parameter expansion** (bash-like operators):

```toml
# Default value if VAR is unset:
tables = "aws dynamodb list-tables --region ${AWS_REGION:-us-east-1}"

# Alternate value if VAR is set:
debug_flag = "server ${DEBUG:+--debug}"
```

**Glob expansion**: Patterns like `*.py`, `**/*.txt` are expanded via Python's glob module.

- `empty_glob = "null"` — treat no-match as empty string (like shell nullglob)
- `empty_glob = "fail"` — fail the task if pattern matches nothing
- `empty_glob = "pass"` — pass pattern through unchanged (default)

**Extra args**: Free args (after `--`) are auto-appended. Use `$POE_EXTRA_ARGS` for explicit placement:

```toml
cmd = "pytest $POE_EXTRA_ARGS --cov=src"  # extra args before --cov, not after
```

---

## script — Python Function

Calls a Python callable in the project's virtual environment. Supports sync and async functions.

Use when: the task needs Python logic, type-safe argument handling, or async operations.

```toml
[tool.poe.tasks.serve]
script = "myapp:run"                             # calls myapp.run()
help = "Start the development server"

[tool.poe.tasks.deploy]
script = "my_pkg.deploy:run(env, dry_run=True)"  # with inline args

[tool.poe.tasks.http-server]
script = "http.server"                           # runs module's __main__
```

When the call expression names a **module** (no `:` or `()`), poe runs `python -m <module>` and any declared args are re-emitted on `sys.argv` (with defaults applied) — useful for delegating to existing CLI modules. With a callable form, declared args are passed as kwargs (no parens) or by reference in the call (with parens). See `args-reference.md` for the full table.

**With task args** (passed as keyword args when no parentheses):

```toml
[tool.poe.tasks.deploy]
script = "deploy:main"
help = "Deploy to an environment"
args = [
  { name = "env", positional = true, choices = ["staging", "production"] },
  { name = "dry_run", type = "boolean", options = ["--dry-run"] }
]
```

**Private args in call expression**:

```toml
script = "deploy:main(_env, dry_run=_dry_run)"
args = [
  { name = "_env", positional = true },
  { name = "_dry_run", type = "boolean", options = ["--dry-run"] }
]
```

**Options**:

- `print_result = true` — print return value to stdout (callable form only; rejected on module form, since `python -m` has no return value)
- Async functions are automatically run with `asyncio.run()`

---

## shell — Shell Script

Runs a full shell script via the configured interpreter. Task args are accessible as environment variables.

Note: only **public** args reach a shell task. Private `_`-prefixed args are deliberately not exported to the environment, so a shell task can't see them — use a `script` or `expr` task if you need to consume a private arg.

Use when: you need shell features — pipes, conditionals, loops, process substitution. Otherwise, prefer `cmd`.

```toml
[tool.poe.tasks.stats]
shell = """
echo "Python files: $(find . -name '*.py' | wc -l)"
echo "Test coverage: $(pytest --co -q 2>/dev/null | tail -1)"
"""
help = "Show project statistics"
```

**Interpreter options** (task-level or global):

```toml
# Task-level:
[tool.poe.tasks.install-win]
shell = "Invoke-WebRequest https://example.com -OutFile pkg.zip"
interpreter = "pwsh"

# Global default:
[tool.poe]
shell_interpreter = "bash"
```

Valid values: `posix` (default — tries sh, bash, zsh), `sh`, `bash`, `zsh`, `fish`, `pwsh`, `powershell`, `python`

---

## sequence — Run Tasks in Order

Executes tasks sequentially; stops on first failure by default. The shorthand is a plain array.

Use when: tasks must run in a specific order (lint → test, build → deploy).

```toml
[tool.poe.tasks]
check = ["lint", "types", "test"]   # shorthand: array of task refs

[tool.poe.tasks.release]
sequence = ["test", "build", "_publish"]
help = "Test, build, and publish"
```

**Mixed inline tasks** (using array of tables):

```toml
[[tool.poe.tasks.check.sequence]]
cmd = "ruff check ."

[[tool.poe.tasks.check.sequence]]
script = "validate:schema"

[[tool.poe.tasks.check.sequence]]
ref = "test"
```

**ignore_fail options**:

- `true` — continue on failure; return 0 if all other tasks succeed
- `"return_zero"` — always return 0 regardless of failures
- `"return_non_zero"` — continue but return non-zero if any task failed

**Forwarding extra args to subtasks**:

```toml
[tool.poe.tasks.check]
sequence = ["lint $POE_EXTRA_ARGS", "test $POE_EXTRA_ARGS"]
```

---

## parallel — Run Tasks Concurrently

Runs all tasks at the same time; output is streamed by default with task-name prefixes in distinct colors.

Use when: tasks are independent and can benefit from concurrency (linting, type checking, tests).

```toml
[tool.poe.tasks.check]
parallel = ["mypy", "pylint", "pytest"]
help = "Run all checks in parallel"
```

**Output prefix customization**:

```toml
[tool.poe.tasks.check]
parallel = ["lint", "test"]
prefix_template = "{color_start}[{prefix}]{color_end} "
prefix_max = 12
```

Available tags: `{name}`, `{index}`, `{color_start}`, `{color_end}`

**output_mode**: by default each subtask's output is streamed line-by-line as it arrives, so lines from different tasks interleave. Set `output_mode = "buffer"` to hold each subtask's stdout and print it as one contiguous block when that subtask finishes:

```toml
[tool.poe.tasks.check]
parallel = ["test-py310", "test-py311"]
output_mode = "buffer"
```

**Redirect a subtask to a file**: set `capture_stdout` on an individual subtask to send its output to a file instead of the prefixed console stream:

```toml
[tool.poe.tasks.checks]
parallel = [
  "lint",
  { cmd = "pytest", capture_stdout = "pytest.log" },
]
```

**ignore_fail**: same options as sequence.

**Nested composition**: sequences can contain parallel tasks and vice versa:

```toml
[tool.poe.tasks.ci]
sequence = [
  { parallel = ["lint", "types"] },   # run checks in parallel first
  "test"                               # then run tests
]
```

---

## ref — Reference Another Task

Calls another task by name, optionally with extra args. Supports parameter expansion including `:-` and `:+` operators. This is the default item type inside sequence/parallel arrays.

Use when: composing tasks inside sequences or parallel blocks with specific args, or aliasing a task with conditional arguments.

```toml
[tool.poe.tasks.ci]
sequence = [
  { ref = "lint" },
  { ref = "test --cov" },      # pass extra args to the referenced task
  { ref = "build" }
]

# Conditional args via expansion:
[tool.poe.tasks.deploy]
ref = "build ${_target:-production}"
args = [{ name = "_target", positional = true, default = "" }]
```

---

## switch — Conditional Execution

Runs different sub-tasks based on a control value. The control task runs first; its output selects the branch.

Use when: behavior differs by platform, environment, or argument value.

```toml
[tool.poe.tasks.install]
help = "Install platform-specific dependencies"
control.expr = "sys.platform"

  [[tool.poe.tasks.install.switch]]
  case = "win32"
  cmd = "install_windows.bat"

  [[tool.poe.tasks.install.switch]]
  case = ["darwin", "linux"]
  cmd = "bash install_unix.sh"

  [[tool.poe.tasks.install.switch]]
  # no case = default branch
  shell = "echo 'Unsupported platform'"
```

**Switch on environment variable or arg**:

```toml
[tool.poe.tasks.deploy]
# ✅ Reference the arg by bare variable name. Do NOT write `${STAGE}` here —
#    that routes through the environment and silently breaks for private args.
control.expr = "STAGE"
args = [{ name = "STAGE", positional = true, choices = ["staging", "production"] }]

  [[tool.poe.tasks.deploy.switch]]
  case = "staging"
  cmd = "deploy --env staging"

  [[tool.poe.tasks.deploy.switch]]
  case = "production"
  cmd = "deploy --env production"
```

**default option**: `"pass"` (succeed silently with no match) or `"fail"` (fail if no case matched). Default is `"fail"`.

**Constraints**:

- Control task type must be `expr`, `cmd`, or `script`.
- Matching is by string comparison: the control output is `str()`-ed and compared against each `case` value (also `str()`-ed).
- `args` declared on the switch task propagate automatically to the control task **and** every case task. Cases may **not** redeclare `args`, `uses`, or `deps`.

**Branching on a private (`_`-prefixed) arg**: in an `expr` control, reference it by **bare variable name**, never `${...}`. Private args aren't exported as env vars, so `control.expr = "${_target}"` silently resolves to an empty string and the switch falls through to `default`. Use the bare-variable form:

```toml
[tool.poe.tasks.deploy]
control.expr = "_target"          # ✅ bare variable — works for both public and private args
# control.expr = "${_target}"     # ❌ broken: ${_target} routes through env, silent empty for private args
args = [{ name = "_target", positional = true, choices = ["dev", "prod"] }]

  [[tool.poe.tasks.deploy.switch]]
  case = "dev"
  cmd = "deploy --env dev"

  [[tool.poe.tasks.deploy.switch]]
  case = "prod"
  cmd = "deploy --env prod"
```

---

## expr — Python Expression

Evaluates a Python expression and prints the result to stdout.

Use when: outputting computed values, platform checks, file counts, or lightweight validation.

> **Common misconception — `${VAR}` is NOT textual substitution.** It is tempting to assume `${STAGE}` gets pasted into the Python source so that `expr = "${STAGE}"` becomes the bare name `staging` and raises `NameError` (so you'd need to "quote it" as `expr = "'${STAGE}'"`). **This is wrong.** `${VAR}` is rewritten to an *attribute reference* on an injected class — internally `${STAGE}` becomes `__env.STAGE`, which evaluates to the string value at runtime. Compare:
>
> - ✅ `expr = "${STAGE}"` → Python source becomes `__env.STAGE` → yields the string value (e.g. `"staging"`).
> - ❌ `expr = "'${STAGE}'"` → Python source becomes `'__env.STAGE'` → yields the **literal string** `"__env.STAGE"` (NOT the value of `STAGE`). The "defensive" outer quotes actively break the expression.
>
> To call a method on the value, do **not** wrap it: `expr = "${STAGE}.upper()"` → `__env.STAGE.upper()` → yields `"STAGING"`. (Writing `"'${STAGE}'.upper()"` would call `.upper()` on the literal string `"__env.STAGE"` and return `"__ENV.STAGE"` — broken.)

**Referencing declared args.** A declared arg is in scope as a **bare Python variable** under its declared name. The canonical form is `expr = "AWS_REGION"`, not `expr = "${AWS_REGION}"`.

> The `${AWS_REGION}` form routes through the *environment* (not the args namespace). For a **public** arg this coincides because public args are also exported to env — but for a **private `_`-prefixed arg it silently breaks**: private args are deliberately not exported, so `${_target}` resolves to an empty/missing env var rather than the arg's value. Always use the bare-variable form when an `expr` references an arg.

See `args-reference.md` for the full per-task-type table.

```toml
[tool.poe.tasks.platform]
expr = "sys.platform"
help = "Print the current platform"

[tool.poe.tasks.count-hidden]
expr = "len(list(pathlib.Path('.').glob('.*')))"
imports = ["pathlib"]
help = "Count hidden files in the project root"
```

**With assert** (fail if result is falsey):

```toml
[tool.poe.tasks.check-venv]
expr = "${VIRTUAL_ENV}.endswith('.venv')"
assert = true
help = "Verify the correct virtualenv is active"
```

**Options**:

- `imports` — list of modules to import before evaluating
- `assert = true` — fail task if result is falsey
- `sys` is always available; Python builtins are available
