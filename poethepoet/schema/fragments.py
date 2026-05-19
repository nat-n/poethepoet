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


def env_option_schema(ctx: SchemaContext) -> dict:
    """
    Build the env option's schema: `{type: object, additionalProperties:
    <string | env_default>}`. Keys are unconstrained env var names.

    Registers env_default in ctx.definitions.
    """
    from poethepoet.config.primitives import EnvDefault
    from poethepoet.options.annotations import TypeAnnotation
    from poethepoet.schema.translate import translate_type

    # Translate EnvDefault as a TypedDict.
    env_default_annotation = TypeAnnotation.parse(EnvDefault)
    env_default_schema = translate_type(env_default_annotation, ctx)
    ctx.register("env_default", env_default_schema)

    value_schema = {
        "anyOf": [
            {"type": "string"},
            {"$ref": "#/definitions/env_default"},
        ]
    }

    result = {
        "type": "object",
        "additionalProperties": value_schema,
    }
    ctx.register("env_option", result)
    return result


def envfile_option_schema(ctx: SchemaContext) -> dict:
    """
    Build the envfile option's schema. Three accepted shapes:
    - Bare string (one envfile path)
    - Array of strings (multiple paths)
    - EnvfileOption TypedDict with expected/optional keys

    Registers envfile_full (the TypedDict shape) in ctx.definitions.
    """
    from poethepoet.config.primitives import EnvfileOption
    from poethepoet.options.annotations import TypeAnnotation
    from poethepoet.schema.translate import translate_type

    envfile_full_annotation = TypeAnnotation.parse(EnvfileOption)
    envfile_full_schema = translate_type(envfile_full_annotation, ctx)
    ctx.register("envfile_full", envfile_full_schema)

    result = {
        "anyOf": [
            {"type": "string"},
            {"type": "array", "items": {"type": "string"}},
            {"$ref": "#/definitions/envfile_full"},
        ]
    }
    ctx.register("envfile_option", result)
    return result


def args_option_schema(ctx: SchemaContext) -> dict:
    """
    Build the args option's schema. Two accepted top-level shapes:
    - List of (string | args_item) — each item declares one argument.
    - Dict mapping arg-name to args_item (with `name` omitted from
      the inner — it's the dict key).

    Registers args_item (the ArgSpec shape) in ctx.definitions.
    """
    from poethepoet.task.args import ArgSpec

    args_item_schema = ArgSpec.__schema_fragment__(ctx)
    ctx.register("args_item", args_item_schema)

    # For the dict form, the `name` key must NOT appear inside each value
    # (it's the dict key). Build a separate args_item_no_name variant.
    args_item_no_name = dict(args_item_schema)
    args_item_no_name["properties"] = {
        key: value
        for key, value in args_item_schema["properties"].items()
        if key != "name"
    }
    args_item_no_name["required"] = sorted(
        key for key in args_item_schema.get("required", []) if key != "name"
    )
    ctx.register("args_item_no_name", args_item_no_name)

    result = {
        "anyOf": [
            {
                "type": "array",
                "items": {
                    "anyOf": [
                        {"type": "string"},
                        {"$ref": "#/definitions/args_item"},
                    ],
                },
            },
            {
                "type": "object",
                "additionalProperties": {
                    "$ref": "#/definitions/args_item_no_name"
                },
            },
        ]
    }
    ctx.register("args_option", result)
    return result


def tasks_map_schema(ctx: SchemaContext) -> dict:
    """
    Build the schema for the `tasks` map: keys match the task-name
    pattern (imported from task/base.py — single source of truth),
    values are task definitions.
    """
    from poethepoet.task.base import _TASK_NAME_PATTERN

    result = {
        "type": "object",
        "additionalProperties": False,
        "patternProperties": {
            _TASK_NAME_PATTERN.pattern: {"$ref": "#/definitions/task_def"},
        },
    }
    ctx.register("tasks_map", result)
    return result


def groups_map_schema(ctx: SchemaContext) -> dict:
    """
    Build the schema for the `groups` map: keys match the group-name
    pattern (imported from config/partition.py — single source of truth),
    values reference the task_group TypedDict.
    """
    from poethepoet.config.partition import _GROUP_NAME_PATTERN, TaskGroup
    from poethepoet.options.annotations import TypeAnnotation
    from poethepoet.schema.translate import translate_type

    task_group_annotation = TypeAnnotation.parse(TaskGroup)
    task_group_schema = translate_type(task_group_annotation, ctx)
    ctx.register("task_group", task_group_schema)

    result = {
        "type": "object",
        "additionalProperties": False,
        "patternProperties": {
            _GROUP_NAME_PATTERN.pattern: {"$ref": "#/definitions/task_group"},
        },
    }
    ctx.register("groups_map", result)
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
