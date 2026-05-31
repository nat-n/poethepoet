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
    include_script_schema,
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
        if branch.get("type") == "object" and "properties" in branch
    ]
    assert len(fallbacks) == 1
    properties = fallbacks[0]["properties"]
    forbidden_keys = {key for key, sub in properties.items() if sub is False}
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


def test_executor_partial_is_anyof_over_per_executor_partials(
    ctx: SchemaContext,
) -> None:
    """
    executor_partial discriminates by property set: each branch is a
    per-executor partial that strips `type` from the full definition.
    Without this structure, the partial would accept any object without
    a type — which is the gap PR #392 flagged.
    """
    executor_option_schema(ctx)
    partial = ctx.definitions["executor_partial"]
    assert "anyOf" in partial
    refs = {b["$ref"] for b in partial["anyOf"] if "$ref" in b}
    # Each registered executor + auto has its own partial twin.
    assert "#/definitions/executor_uv_partial" in refs
    assert "#/definitions/executor_virtualenv_partial" in refs
    assert "#/definitions/executor_auto_partial" in refs


def test_executor_uv_partial_strips_type_keeps_other_options(
    ctx: SchemaContext,
) -> None:
    """
    The per-executor partial mirrors the full definition's properties
    except for `type`, with `type` no longer in `required`.
    """
    executor_option_schema(ctx)
    partial = ctx.definitions["executor_uv_partial"]
    assert "type" not in partial["properties"]
    assert "isolated" in partial["properties"]
    assert "required" not in partial or "type" not in partial.get("required", [])
    assert partial["additionalProperties"] is False


def test_executor_partial_rejects_unknown_keys() -> None:
    """
    End-to-end: a task-level executor partial with a typo'd key (no
    `type`) should be rejected. Before this fix, the schema accepted
    `{garbage: "value"}` because executor_partial was a permissive
    `{type:object, not:{required:[type]}}`.
    """
    from jsonschema import Draft7Validator

    from poethepoet.schema.generator import build_schema

    validator = Draft7Validator(build_schema())
    bad_config = {"tasks": {"t": {"cmd": "x", "executor": {"garbage": "value"}}}}
    assert list(validator.iter_errors(bad_config))


def test_executor_partial_accepts_empty_object() -> None:
    """
    `executor = {}` at the task level is a no-op partial that defers
    everything to the project/group context — must remain accepted.
    """
    from jsonschema import Draft7Validator

    from poethepoet.schema.generator import build_schema

    validator = Draft7Validator(build_schema())
    ok_config = {"tasks": {"t": {"cmd": "x", "executor": {}}}}
    assert not list(validator.iter_errors(ok_config))


def test_executor_partial_accepts_executor_specific_override() -> None:
    """
    A task-level partial naming a uv-specific option (`isolated`) must
    match the uv branch — i.e., the partial union discriminates by
    property set, not just by absence of `type`.
    """
    from jsonschema import Draft7Validator

    from poethepoet.schema.generator import build_schema

    validator = Draft7Validator(build_schema())
    ok_config = {"tasks": {"t": {"cmd": "x", "executor": {"isolated": True}}}}
    assert not list(validator.iter_errors(ok_config))


def test_executor_partial_rejects_keys_mixing_two_executors() -> None:
    """
    Combining keys from two different executors (uv's `isolated` and
    virtualenv's `location`) makes no sense — the partial should reject
    it. Each per-executor partial has `additionalProperties:false`, so
    no single branch in the anyOf accepts both keys.
    """
    from jsonschema import Draft7Validator

    from poethepoet.schema.generator import build_schema

    validator = Draft7Validator(build_schema())
    bad_config = {
        "tasks": {
            "t": {
                "cmd": "x",
                "executor": {"isolated": True, "location": "/x"},
            }
        }
    }
    assert list(validator.iter_errors(bad_config))


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
    """
    envfile_option has three top-level shapes (bare string, array,
    envfile_full TypedDict). The array branch accepts items that are
    themselves string OR envfile_full, mirroring the runtime type
    ``str | EnvfileOption | Sequence[str | EnvfileOption]``.
    """
    schema = envfile_option_schema(ctx)
    assert "oneOf" in schema
    branches = schema["oneOf"]
    assert {"type": "string"} in branches
    assert any("$ref" in b for b in branches)
    array_branches = [b for b in branches if b.get("type") == "array"]
    assert len(array_branches) == 1
    items = array_branches[0]["items"]
    assert "oneOf" in items, f"Expected mixed-item array, got {items!r}"
    item_alts = items["oneOf"]
    assert {"type": "string"} in item_alts
    assert any("$ref" in alt for alt in item_alts)


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


def test_include_script_item_executor_references_executor_task_option(
    ctx: SchemaContext,
) -> None:
    """
    Include_script entries accept executor objects; the schema should
    direct them to the discriminated executor union, not a bare object.
    """
    executor_option_schema(ctx)
    include_script_schema(ctx)
    item = ctx.definitions["include_script_item"]
    assert item["properties"]["executor"] == {
        "$ref": "#/definitions/executor_task_option"
    }


def test_include_script_array_items_reference_include_script_item(
    ctx: SchemaContext,
) -> None:
    """
    The array branch of include_script lists either string shorthand or
    a `$ref` to the dict-form item definition — not an inlined object.
    """
    executor_option_schema(ctx)
    schema = include_script_schema(ctx)
    array_branch = next(
        branch for branch in schema["anyOf"] if branch.get("type") == "array"
    )
    inner = array_branch["items"]["anyOf"]
    assert {"$ref": "#/definitions/include_script_item"} in inner


def test_task_group_executor_references_executor_task_option() -> None:
    """
    After build_schema runs, task_group.executor should be a $ref to the
    discriminated executor union — same target the per-task case uses.
    """
    from poethepoet.schema.generator import build_schema

    schema = build_schema()
    task_group = schema["definitions"]["task_group"]
    assert task_group["properties"]["executor"] == {
        "$ref": "#/definitions/executor_task_option"
    }


def test_task_group_tasks_references_tasks_map() -> None:
    """
    task_group.tasks should reference tasks_map so nested-in-group tasks
    get the same patternProperties + task_def validation that top-level
    tasks get.
    """
    from poethepoet.schema.generator import build_schema

    schema = build_schema()
    task_group = schema["definitions"]["task_group"]
    assert task_group["properties"]["tasks"] == {"$ref": "#/definitions/tasks_map"}


def test_root_include_script_uses_ref() -> None:
    """
    The root include_script property emits a $ref to the registered
    definition rather than inlining the union.
    """
    from poethepoet.schema.generator import build_schema

    schema = build_schema()
    root_include_script = schema["properties"]["include_script"]
    assert root_include_script["$ref"] == "#/definitions/include_script"


def test_schema_rejects_unknown_group_executor_type() -> None:
    """
    A group declaring an executor object with a `type` not in the
    registry should be rejected by the schema. The runtime only catches
    this when the executor actually runs, but the schema catches it at
    edit time — which is the whole point of the discriminated union.
    """
    from jsonschema import Draft7Validator

    from poethepoet.schema.generator import build_schema

    validator = Draft7Validator(build_schema())
    bad_config = {
        "groups": {
            "mygroup": {
                "heading": "mygroup",
                "executor": {"type": "totally_invalid_executor"},
            }
        }
    }
    assert list(validator.iter_errors(bad_config))


def test_schema_rejects_structurally_broken_task_inside_group() -> None:
    """
    Nested-in-group tasks must validate against task_def. Before the
    tasks_map ref swap, this was a free-form object — IDEs gave zero
    structural feedback on tasks declared inside a group.
    """
    from jsonschema import Draft7Validator

    from poethepoet.schema.generator import build_schema

    validator = Draft7Validator(build_schema())
    bad_config = {
        "groups": {
            "mygroup": {
                "heading": "mygroup",
                "tasks": {"mytask": {"cmd": 9999}},
            }
        }
    }
    assert list(validator.iter_errors(bad_config))


def test_schema_rejects_unknown_include_script_executor_type() -> None:
    """
    include_script items had a bare `{anyOf: [string, object]}` executor
    field before the ref swap — any object slipped through. Now the
    discriminated union applies.
    """
    from jsonschema import Draft7Validator

    from poethepoet.schema.generator import build_schema

    validator = Draft7Validator(build_schema())
    bad_config = {
        "include_script": [
            {
                "script": "tasks:tasks1",
                "executor": {"type": "totally_invalid_executor"},
            }
        ]
    }
    assert list(validator.iter_errors(bad_config))
