"""
Unit tests for cross-cutting schema fragments — task_def union,
executor tagged union, env/envfile polymorphism, tasks/groups maps.
"""

from __future__ import annotations

import pytest

from poethepoet.schema.context import SchemaContext
from poethepoet.schema.fragments import (
    args_option_schema,
    env_option_schema,
    envfile_option_schema,
    executor_option_schema,
    groups_map_schema,
    task_def_schema,
    task_def_with_case_schema,
    tasks_map_schema,
)


@pytest.fixture
def ctx() -> SchemaContext:
    return SchemaContext(version="0.0.0")


def test_task_def_includes_string_branch(ctx: SchemaContext) -> None:
    """Bare string is one of the accepted shapes."""
    schema = task_def_schema(ctx)
    string_branches = [
        branch for branch in schema["oneOf"] if branch.get("type") == "string"
    ]
    assert len(string_branches) == 1


def test_task_def_includes_array_branch(ctx: SchemaContext) -> None:
    """Bare array is one of the accepted shapes."""
    schema = task_def_schema(ctx)
    array_branches = [
        branch for branch in schema["oneOf"] if branch.get("type") == "array"
    ]
    assert len(array_branches) == 1
    # Items recurse into task_def.
    assert array_branches[0]["items"] == {"$ref": "#/definitions/task_def"}


def test_task_def_includes_branch_per_registered_task_type(ctx: SchemaContext) -> None:
    """
    Each task type registered via MetaPoeTask appears as a $ref branch.
    """
    from poethepoet.task.base import PoeTask

    schema = task_def_schema(ctx)
    refs = {branch["$ref"] for branch in schema["oneOf"] if "$ref" in branch}
    expected_refs = {f"#/definitions/{key}_task" for key in PoeTask.get_task_types()}
    assert expected_refs.issubset(refs)


def test_task_def_includes_forward_compat_fallback(ctx: SchemaContext) -> None:
    """
    The fallback branch accepts any object that doesn't contain a known
    discriminator key — forward compatibility with future task types.
    """
    from poethepoet.task.base import PoeTask

    schema = task_def_schema(ctx)
    fallbacks = [
        branch
        for branch in schema["oneOf"]
        if branch.get("type") == "object" and "not" in branch
    ]
    assert len(fallbacks) == 1
    not_clause = fallbacks[0]["not"]
    assert "anyOf" in not_clause
    forbidden_keys = {clause["required"][0] for clause in not_clause["anyOf"]}
    assert forbidden_keys == set(PoeTask.get_task_types())


def test_task_def_registers_per_task_definitions_in_ctx(ctx: SchemaContext) -> None:
    """
    After calling task_def_schema(ctx), the context's definitions should
    contain entries for every task variant (cmd_task, shell_task, etc.).
    """
    task_def_schema(ctx)
    from poethepoet.task.base import PoeTask

    for key in PoeTask.get_task_types():
        assert f"{key}_task" in ctx.definitions


def test_task_def_with_case_schema_has_case_key_in_each_variant(
    ctx: SchemaContext,
) -> None:
    """
    Every task variant inside task_def_with_case gains an optional
    `case` key (used by switch).
    """
    # task_def_with_case depends on task_def_schema having run first.
    task_def_schema(ctx)
    task_def_with_case_schema(ctx)
    # The forward-compat fallback may not have an explicit `case` key
    # (its `additionalProperties: true` covers it). Focus on the
    # explicit variants by looking at the registered _task_with_case defs.
    from poethepoet.task.base import PoeTask

    for key in PoeTask.get_task_types():
        variant = ctx.definitions[f"{key}_task_with_case"]
        assert (
            "case" in variant["properties"]
        ), f"{key}_task_with_case should have a `case` property"


def test_task_def_schema_registers_itself(ctx: SchemaContext) -> None:
    schema = task_def_schema(ctx)
    assert ctx.definitions["task_def"] == schema


def test_executor_option_includes_shorthand_string(ctx: SchemaContext) -> None:
    """A bare string like "poetry" or "auto" should be accepted."""
    schema = executor_option_schema(ctx)
    string_branches = [
        b for b in schema["oneOf"] if b.get("type") == "string" and "enum" in b
    ]
    assert len(string_branches) == 1
    # Contains each registered executor key plus "auto".
    enum_values = set(string_branches[0]["enum"])
    assert "auto" in enum_values
    assert "poetry" in enum_values
    assert "uv" in enum_values


def test_executor_option_includes_per_executor_dict_branches(
    ctx: SchemaContext,
) -> None:
    schema = executor_option_schema(ctx)
    ref_branches = {b["$ref"] for b in schema["oneOf"] if "$ref" in b}
    # Each registered executor has its own definition.
    assert "#/definitions/executor_poetry" in ref_branches
    assert "#/definitions/executor_uv" in ref_branches


def test_executor_uv_type_is_const_uv(ctx: SchemaContext) -> None:
    """The `type` field on uv's executor branch is constrained."""
    executor_option_schema(ctx)  # populates ctx.definitions
    uv_schema = ctx.definitions["executor_uv"]
    assert uv_schema["properties"]["type"] in (
        {"type": "string", "enum": ["uv"]},
        {"const": "uv"},
    )


def test_env_option_schema_accepts_string_and_env_default_values(
    ctx: SchemaContext,
) -> None:
    schema = env_option_schema(ctx)
    assert schema["type"] == "object"
    # additionalProperties is a union: string OR env_default $ref
    ap = schema["additionalProperties"]
    assert "anyOf" in ap
    branches = ap["anyOf"]
    assert {"type": "string"} in branches
    assert any("$ref" in b and b["$ref"].endswith("env_default") for b in branches)


def test_env_default_registered(ctx: SchemaContext) -> None:
    env_option_schema(ctx)
    assert "env_default" in ctx.definitions
    env_default = ctx.definitions["env_default"]
    # The property schema may include a description; check the type is correct.
    assert env_default["properties"]["default"]["type"] == "string"
    assert env_default["required"] == ["default"]


def test_envfile_option_schema_includes_three_shapes(ctx: SchemaContext) -> None:
    schema = envfile_option_schema(ctx)
    assert "anyOf" in schema
    branches = schema["anyOf"]
    # Bare string, array of strings, envfile_full TypedDict
    assert {"type": "string"} in branches
    assert any(
        b.get("type") == "array" and b.get("items") == {"type": "string"}
        for b in branches
    )
    assert any("$ref" in b for b in branches)


def test_args_option_schema_accepts_list_or_dict(ctx: SchemaContext) -> None:
    schema = args_option_schema(ctx)
    assert "anyOf" in schema
    branches = schema["anyOf"]
    # List form: array of (string | args_item)
    list_branches = [b for b in branches if b.get("type") == "array"]
    assert list_branches
    # Dict form: object mapping arg-name to args_item
    dict_branches = [b for b in branches if b.get("type") == "object"]
    assert dict_branches


def test_args_item_registered(ctx: SchemaContext) -> None:
    """The per-arg ArgSpec shape is in definitions."""
    args_option_schema(ctx)
    assert "args_item" in ctx.definitions


def test_tasks_map_schema_has_pattern_properties(ctx: SchemaContext) -> None:
    import re

    schema = tasks_map_schema(ctx)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "patternProperties" in schema
    # Exactly one pattern entry — the task-name regex.
    assert len(schema["patternProperties"]) == 1
    pattern, _value_schema = next(iter(schema["patternProperties"].items()))
    # Pattern starts with letter or underscore.
    compiled = re.compile(pattern)
    assert compiled.fullmatch("my_task")
    assert compiled.fullmatch("Task-1")
    assert not compiled.fullmatch("1bad")  # digit-first rejected
    assert not compiled.fullmatch("bad name")  # space rejected


def test_tasks_map_values_reference_task_def(ctx: SchemaContext) -> None:
    task_def_schema(ctx)  # populate task_def first
    schema = tasks_map_schema(ctx)
    value_schema = next(iter(schema["patternProperties"].values()))
    assert value_schema == {"$ref": "#/definitions/task_def"}


def test_groups_map_schema_imports_group_name_pattern(ctx: SchemaContext) -> None:
    from poethepoet.config.partition import _GROUP_NAME_PATTERN

    schema = groups_map_schema(ctx)
    pattern = next(iter(schema["patternProperties"].keys()))
    # The pattern from the constant should be the same regex.
    assert pattern == _GROUP_NAME_PATTERN.pattern


def test_groups_map_values_reference_task_group(ctx: SchemaContext) -> None:
    schema = groups_map_schema(ctx)
    value_schema = next(iter(schema["patternProperties"].values()))
    assert value_schema == {"$ref": "#/definitions/task_group"}
