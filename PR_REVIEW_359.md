# Review of PR #359: Treat `False` Flag Argument as Undefined

## Summary

This PR addresses issue #357 by changing how boolean flag arguments are handled
across all task types. The core idea: `False` boolean flags should behave as
"unset" in cmd/shell tasks (expanding to empty string `""`), enabling intuitive
use of parameter expansion operators (`:-`, `:+`). In script/expr tasks, `False`
remains the Python `False` value.

## Architecture

The approach introduces a layered design:

1. **`EnvVarsManager._vars`** now stores `bool` values natively (not stringified)
2. **`CmdEnvVarsReader`** wraps the env as a `Mapping[str, str]`, converting
   `False` → `""` and `True` → `"True"` at the boundary
3. **`args.py`** always sets `default = False` for boolean args without an
   explicit default (previously `None`/implicit)

This is a sound architectural choice — it preserves type information through the
pipeline and converts at the appropriate boundary depending on the task type.

---

## Issues Found

### 1. Documentation example has a leading-space bug

**File:** `docs/tasks/task_types/cmd.rst`

```toml
[tool.poe.tasks.greet]
cmd = "echo ${hello:- hello!}"
args = [{ name = "hello", type = "boolean", default = "hi!" }]
```

The description says: *"it prints 'hello!' if the --hello flag is present"*.

But `${hello:- hello!}` has a space after `:-`, so when `--hello` is provided
(value becomes `False` → `""`), the expansion produces `" hello!"` with a
leading space. The echo output would be ` hello!`, not `hello!`.

Should be either:
- `${hello:-hello!}` (no space after `:-`), or
- The description should acknowledge the leading space

### 2. `to_dict()` removal is a breaking change

The PR removes `EnvVarsManager.to_dict()` entirely and replaces all internal
calls with `to_cmd_reader()`. Even though `to_dict()` was likely not part of a
public API contract, it could break downstream code that depends on it (plugins,
custom executors, etc.). Consider either:

- Keeping `to_dict()` as a deprecated alias, or
- Documenting this as a breaking change

### 3. `with_special_case` parameter naming is unclear

```python
def to_cmd_reader(self, *, with_special_case: bool = False) -> CmdEnvVarsReader:
    return CmdEnvVarsReader(self if with_special_case else self._vars)
```

The "special case" refers to `POE_GIT_DIR` and `POE_GIT_ROOT` lazy-loading in
`EnvVarsManager.get()`. A clearer name would be `with_lazy_vars` or
`include_special_vars` to communicate what the flag actually controls.

### 4. `expr.py` change may alter `${VAR}` behavior in expr tasks

```python
# Before:
expression, accessed_vars = self._substitute_env_vars(
    self.spec.content.strip(), env.to_dict()
)
# After:
expression, accessed_vars = self._substitute_env_vars(
    self.spec.content.strip(), env.to_cmd_reader()
)
```

In expr tasks, `${VAR}` references get substituted into `__env.VAR` attributes.
The `accessed_vars` dict captures values from the env at substitution time.
Previously, a `False` boolean arg in the env would have been stringified to
`"False"` by `to_dict()` → `__env.VAR` would be `"False"` (truthy string).
Now, via `to_cmd_reader()`, it becomes `""` (empty/falsy string).

This matters if someone uses `${bool_arg}` template syntax in an expr task
(rather than direct variable references). The tests only exercise direct variable
references like `{'non':non}`, not `${non}` template references, so this edge
case is untested.

Consider either:
- Adding a test for `${bool_arg}` in expr tasks, or
- Not using `to_cmd_reader()` in expr.py (pass the raw dict and let the existing
  `str()` conversion handle it)

### 5. `bool_to_str` should be a `@staticmethod`

```python
@classmethod
def bool_to_str(cls, value: bool) -> str:
    return "" if value is False else str(value)
```

This method doesn't use `cls`. It should be `@staticmethod`.

### 6. Missing newline at end of several fixture files

The following fixture files are missing a trailing newline:
- `tests/fixtures/cmds_project/pyproject.toml`
- `tests/fixtures/shells_project/pyproject.toml`
- `tests/fixtures/switch_project/pyproject.toml`

### 7. Parent env inheritance flattens booleans

```python
# In __init__:
self._vars = {
    **(parent_env.to_cmd_reader() if parent_env is not None else {}),
    **(base_env or {}),
}
```

When a child `EnvVarsManager` inherits from a parent, `to_cmd_reader()` converts
`False` → `""` and `True` → `"True"`. This means child environments lose the
native bool type. For sequence tasks with mixed subtask types (e.g., a cmd
subtask followed by an expr subtask), the expr subtask's child env would have
`""` instead of `False` for boolean args.

This may be acceptable since subtasks don't have their own args, but it's worth
considering whether the bool values should be preserved through inheritance (use
`parent_env._vars.copy()` or similar) and only convert at the execution boundary.

---

## Design Questions for the Maintainer

### Is the `type(value) is bool` check intentional over `isinstance`?

```python
elif type(value) is bool:
    new_vars[key] = value
```

Using `type(value) is bool` excludes bool subclasses. This is probably fine since
argparse returns native `bool`, but `isinstance(value, bool)` would be more
Pythonic unless there's a specific reason to exclude subclasses (e.g., numpy
bool). Note that `isinstance(1, bool)` is `False` since `int` is not a subclass
of `bool` — wait, actually `bool` is a subclass of `int` in Python, so
`isinstance(True, int)` is `True`. The `type() is bool` check is actually the
correct choice here to avoid treating `int` values as bools.

### Should shell tasks get their own handling?

Shell tasks pass the script content as stdin to the shell interpreter, and env
vars are passed as actual environment variables to the subprocess. The boolean →
string conversion happens in the executor via `to_cmd_reader()`. Since real
environment variables are always strings, `False` → `""` makes sense. But the
shell itself might then do its own parameter expansion on `${VAR:-default}`,
which would also treat `""` as unset. This double-expansion (poe + shell) could
lead to unexpected behavior. The tests seem to validate this works, but it's
worth noting.

---

## Positive Aspects

- **Thorough test coverage**: Tests cover all 6 task types (cmd, shell, expr,
  script, sequence, switch) with both flag-provided and default-value scenarios
- **Consistent behavior**: The change makes `default = false` and no-default
  cases behave identically, which was the core issue
- **Parameter expansion compatibility**: `False` → `""` correctly triggers `:-`
  and suppresses `:+` operators, matching shell semantics
- **Backward compatibility for non-boolean args**: The change only affects
  boolean-typed arguments; string/int/float args are unaffected
- **Documentation updates**: Both the args guide and cmd task docs are updated

---

## Verdict

The PR addresses a real usability issue and the overall approach is sound. The
main concerns are:
1. The documentation example bug (leading space)
2. The untested `${VAR}` edge case in expr tasks
3. The `to_dict()` removal as a breaking change
4. The unclear `with_special_case` naming

I'd recommend addressing items 1-3 before merging.
