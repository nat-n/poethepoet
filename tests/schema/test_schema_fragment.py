"""
Unit tests for PoeOptions.__schema_fragment__ (default) and the
overrides on PoeTask and per-task subclasses.
"""

from __future__ import annotations

from typing import Annotated

import pytest

from poethepoet.options import PoeOptions
from poethepoet.options.annotations import Metadata
from poethepoet.schema.context import SchemaContext


@pytest.fixture
def ctx() -> SchemaContext:
    return SchemaContext(version="0.0.0")


class _Required(PoeOptions):
    name: str
    """The required name."""

    count: int = 0
    """The optional count (has a default)."""


class _Optional(PoeOptions):
    flag: bool | None = None
    """Optional flag."""


def test_default_emits_object_with_properties(ctx: SchemaContext) -> None:
    schema = _Required.__schema_fragment__(ctx)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"name", "count"}


def test_default_marks_required_fields(ctx: SchemaContext) -> None:
    """
    A field without a class-level default and without Optional type
    is required.
    """
    schema = _Required.__schema_fragment__(ctx)
    assert schema["required"] == ["name"]
    # `count` has a default of 0 → not required.


def test_default_attaches_descriptions(ctx: SchemaContext) -> None:
    schema = _Required.__schema_fragment__(ctx)
    assert schema["properties"]["name"]["description"] == "The required name."
    assert schema["properties"]["count"]["description"] == (
        "The optional count (has a default)."
    )


def test_default_excludes_optional_field_from_required(ctx: SchemaContext) -> None:
    schema = _Optional.__schema_fragment__(ctx)
    assert "required" in schema
    assert "flag" not in schema["required"]


def test_default_handles_metadata_constraints(ctx: SchemaContext) -> None:
    class _Constrained(PoeOptions):
        name: Annotated[str, Metadata(pattern=r"^[a-z]+$")] = ""
        """Lowercase name."""

    schema = _Constrained.__schema_fragment__(ctx)
    assert schema["properties"]["name"]["pattern"] == "^[a-z]+$"


def test_default_uses_config_name_for_property_key(ctx: SchemaContext) -> None:
    """
    When a field has Metadata(config_name=...), the schema property key
    must be the config_name, not the Python attribute name.
    """

    class _Renamed(PoeOptions):
        with_: Annotated[str, Metadata(config_name="with")] = ""

    schema = _Renamed.__schema_fragment__(ctx)
    assert "with" in schema["properties"]
    assert "with_" not in schema["properties"]


def test_default_inherits_fields_from_base_class(ctx: SchemaContext) -> None:
    """
    Approach B — full inlining. A subclass's schema_fragment contains
    both its own fields and inherited fields.
    """

    class _Child(_Required):
        extra: str = ""

    schema = _Child.__schema_fragment__(ctx)
    assert set(schema["properties"]) == {"name", "count", "extra"}


def test_cmd_task_schema_fragment_includes_discriminator(ctx: SchemaContext) -> None:
    from poethepoet.task.cmd import CmdTask

    schema = CmdTask.__schema_fragment__(ctx)
    assert schema["type"] == "object"
    assert "cmd" in schema["properties"]
    assert schema["properties"]["cmd"]["type"] == "string"
    assert "cmd" in schema["required"]
    assert schema["additionalProperties"] is False


def test_cmd_task_schema_fragment_includes_standard_options(ctx: SchemaContext) -> None:
    """
    Approach B — full inlining. CmdTask's schema should include all
    fields inherited from PoeTask.TaskOptions.
    """
    from poethepoet.task.cmd import CmdTask

    schema = CmdTask.__schema_fragment__(ctx)
    # Sampled inherited fields:
    for inherited in ("args", "cwd", "env", "deps", "help"):
        assert (
            inherited in schema["properties"]
        ), f"{inherited} should appear inlined on cmd_task"


def test_cmd_task_schema_includes_own_options(ctx: SchemaContext) -> None:
    """CmdTask adds use_exec, empty_glob, ignore_fail."""
    from poethepoet.task.cmd import CmdTask

    schema = CmdTask.__schema_fragment__(ctx)
    assert "use_exec" in schema["properties"]
    assert "empty_glob" in schema["properties"]
    assert "ignore_fail" in schema["properties"]


def test_shell_task_discriminator_is_string() -> None:
    """Validates the discriminator type matches __content_type__."""
    from poethepoet.task.shell import ShellTask

    assert ShellTask.__content_type__ is str


def test_sequence_task_discriminator_is_array(ctx: SchemaContext) -> None:
    """
    For Sequence/Parallel, __content_type__ is list — the discriminator
    appears with `type: array`. Detailed content shape (recursive
    task_def items) is handled by the per-class override in Task 11.
    """
    from poethepoet.task.sequence import SequenceTask

    schema = SequenceTask.__schema_fragment__(ctx)
    # The discriminator key is `sequence` and it must be present and
    # typed as array (the items refinement is the next task).
    assert "sequence" in schema["properties"]
    assert schema["properties"]["sequence"]["type"] == "array"
    assert "sequence" in schema["required"]


def test_switch_task_items_reference_task_def_with_case(ctx: SchemaContext) -> None:
    """
    SwitchTask's `switch` content is a list of case-items, each of which
    is a task definition extended with an optional `case` key. The schema
    references a dedicated `task_def_with_case` definition. The override
    wraps the reference in allOf alongside subtask-option blocklist
    constraints; this test only asserts the reference is present.
    """
    from poethepoet.task.switch import SwitchTask

    schema = SwitchTask.__schema_fragment__(ctx)
    branches = schema["properties"]["switch"]["items"]["allOf"]
    assert {"$ref": "#/definitions/task_def_with_case"} in branches


def test_switch_task_includes_control_property(ctx: SchemaContext) -> None:
    """SwitchTask's TaskOptions has a `control` field that must appear."""
    from poethepoet.task.switch import SwitchTask

    schema = SwitchTask.__schema_fragment__(ctx)
    assert "control" in schema["properties"]
    assert "control" in schema["required"]


def test_sequence_items_reference_task_def(ctx: SchemaContext) -> None:
    from poethepoet.task.sequence import SequenceTask

    schema = SequenceTask.__schema_fragment__(ctx)
    branches = schema["properties"]["sequence"]["items"]["allOf"]
    assert {"$ref": "#/definitions/task_def"} in branches


def test_parallel_items_reference_task_def(ctx: SchemaContext) -> None:
    from poethepoet.task.parallel import ParallelTask

    schema = ParallelTask.__schema_fragment__(ctx)
    branches = schema["properties"]["parallel"]["items"]["allOf"]
    assert {"$ref": "#/definitions/task_def"} in branches


def test_argspec_schema_fragment_has_expected_properties(ctx: SchemaContext) -> None:
    from poethepoet.task.args import ArgSpec

    schema = ArgSpec.__schema_fragment__(ctx)
    expected = {
        "default",
        "help",
        "name",
        "options",
        "positional",
        "required",
        "type",
        "multiple",
        "choices",
    }
    assert set(schema["properties"]) >= expected


def test_argspec_options_field_not_in_required(ctx: SchemaContext) -> None:
    """
    `options` is normalizer-supplied; users typically don't write it
    directly. Mark it optional in the schema.
    """
    from poethepoet.task.args import ArgSpec

    schema = ArgSpec.__schema_fragment__(ctx)
    assert "options" not in schema["required"]


def test_argspec_type_field_is_enum_of_string_float_integer_boolean(
    ctx: SchemaContext,
) -> None:
    """
    `type` is Literal["string", "float", "integer", "boolean"], so the
    schema property should be `{type: string, enum: [...]}`.
    """
    from poethepoet.task.args import ArgSpec

    schema = ArgSpec.__schema_fragment__(ctx)
    type_schema = schema["properties"]["type"]
    assert type_schema["type"] == "string"
    assert set(type_schema["enum"]) == {"string", "float", "integer", "boolean"}
