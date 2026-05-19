"""
Unit tests for cross-cutting schema fragments — task_def union,
executor tagged union, env/envfile polymorphism, tasks/groups maps.
"""

from __future__ import annotations

import pytest

from poethepoet.schema.context import SchemaContext
from poethepoet.schema.fragments import (
    task_def_schema,
    task_def_with_case_schema,
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
