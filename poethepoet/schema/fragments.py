"""
Cross-cutting JSON Schema fragments that aren't owned by any single
PoeOptions class — the task_def union (incl. forward-compat fallback),
the executor tagged union, env/envfile value polymorphism, and the
patternProperties for the tasks/groups maps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from poethepoet.schema.context import SchemaContext


def task_def_schema(ctx: SchemaContext) -> dict:
    """
    Build the task_def union — every accepted shape for "a task" in
    poe config: bare string (default_task_type), bare array
    (default_array_task_type), dict with a recognized discriminator key,
    or dict with no recognized key (forward-compat fallback).

    Side effect: each task variant's schema is registered in
    ctx.definitions, plus task_def itself is registered (so recursive
    `{"$ref": "#/definitions/task_def"}` resolves).
    """
    from poethepoet.task.base import PoeTask

    # Register each task variant under "<key>_task" in $defs.
    task_keys = sorted(PoeTask.get_task_types())
    for key in task_keys:
        task_cls = PoeTask.get_task_class(key)
        ctx.register(f"{key}_task", task_cls.__schema_fragment__(ctx))

    branches: list[dict] = [
        {"type": "string"},
        {
            "type": "array",
            "items": {"$ref": "#/definitions/task_def"},
        },
    ]

    branches.extend({"$ref": f"#/definitions/{key}_task"} for key in task_keys)

    # Forward-compat fallback: a dict that has none of the known
    # discriminator keys.
    branches.append(
        {
            "type": "object",
            "additionalProperties": True,
            "not": {
                "anyOf": [{"required": [key]} for key in task_keys],
            },
        }
    )

    result = {"oneOf": branches}
    ctx.register("task_def", result)
    return result


def executor_option_schema(ctx: SchemaContext) -> dict:
    """
    Build the executor option's discriminated union — over the `type:`
    field. Each registered executor becomes a `#/definitions/executor_<key>`.
    A shorthand string form accepts the bare type name (`"poetry"`,
    `"auto"`, etc.).

    "auto" is a known exception: it's the user-facing default but is
    handled specially by PoeExecutor.validate_config rather than being
    registered as a PoeExecutor subclass. We synthesize a minimal
    executor_auto definition for it.

    Side effect: registers each per-executor definition in ctx.definitions
    and registers the executor_option definition itself.
    """
    from poethepoet.executor.base import PoeExecutor

    executor_keys = sorted(PoeExecutor.get_executor_types())
    # Include "auto" in the shorthand-string enum even though it isn't
    # in the registry.
    enum_keys = sorted(set(executor_keys) | {"auto"})

    branches: list[dict] = [
        {"type": "string", "enum": enum_keys},
    ]

    for key in executor_keys:
        executor_cls = PoeExecutor.get_executor_class(key)
        executor_schema = executor_cls.ExecutorOptions.__schema_fragment__(ctx)
        # Tighten the `type` property to a single-value enum (const
        # equivalent in draft-07).
        executor_schema["properties"] = dict(executor_schema["properties"])
        executor_schema["properties"]["type"] = {
            "type": "string",
            "enum": [key],
        }
        ctx.register(f"executor_{key}", executor_schema)
        branches.append({"$ref": f"#/definitions/executor_{key}"})

    # Synthesize a minimal executor_auto definition since "auto" isn't a
    # registered class.
    ctx.register("executor_auto", {
        "type": "object",
        "additionalProperties": False,
        "required": ["type"],
        "properties": {"type": {"type": "string", "enum": ["auto"]}},
    })
    branches.append({"$ref": "#/definitions/executor_auto"})

    result = {"oneOf": branches}
    ctx.register("executor_option", result)
    return result


def task_def_with_case_schema(ctx: SchemaContext) -> dict:
    """
    Like task_def, but every explicit task-variant branch additionally
    accepts an optional `case` key. Used inside switch tasks.

    The case key accepts either a single string or a list of strings.

    Precondition: task_def_schema(ctx) must have been called first so
    the per-task `<key>_task` variants are in ctx.definitions.
    """
    from poethepoet.task.base import PoeTask

    case_value_schema = {
        "anyOf": [
            {"type": "string"},
            {"type": "array", "items": {"type": "string"}},
        ]
    }

    task_keys = sorted(PoeTask.get_task_types())
    branches: list[dict] = []

    for key in task_keys:
        # Pull the variant's full schema from ctx.definitions and copy it
        # before mutating (definitions returns a fresh dict each call).
        variant = dict(ctx.definitions[f"{key}_task"])
        # Properties is a dict; copy and add `case`.
        variant["properties"] = dict(variant["properties"])
        variant["properties"]["case"] = case_value_schema
        # Register under a distinct name so editor tooling can jump
        # to either form.
        ctx.register(f"{key}_task_with_case", variant)
        branches.append({"$ref": f"#/definitions/{key}_task_with_case"})

    # Forward-compat fallback — same shape as in task_def_schema.
    branches.append(
        {
            "type": "object",
            "additionalProperties": True,
            "not": {
                "anyOf": [{"required": [key]} for key in task_keys],
            },
        }
    )

    return {"oneOf": branches}
