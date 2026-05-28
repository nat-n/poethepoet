"""
Tests for PoeOptions.description_for_field — class-attribute docstring
extraction.
"""

from poethepoet.options import PoeOptions


class DescribedOptions(PoeOptions):
    foo: str = ""
    """The foo field — should be discoverable."""

    bar: int = 0
    """Multi-line description
    spanning two lines."""

    baz: bool = False  # no docstring


class ChildOptions(DescribedOptions):
    foo: str = "override"
    """Overridden description for foo."""

    qux: str = ""
    """Qux on the child only."""


class GrandchildOptions(ChildOptions):
    """Class-level docstring; not a field docstring."""

    # foo is inherited from ChildOptions; description should follow MRO
    new_field: str = ""
    """A field defined only here."""


def test_description_extracted_from_simple_docstring():
    assert (
        DescribedOptions.description_for_field("foo")
        == "The foo field — should be discoverable."
    )


def test_description_extracted_from_multiline_docstring():
    description = DescribedOptions.description_for_field("bar")
    assert description is not None
    assert "Multi-line description" in description
    assert "spanning two lines" in description


def test_description_is_none_when_no_docstring():
    assert DescribedOptions.description_for_field("baz") is None


def test_description_returns_none_for_unknown_field():
    assert DescribedOptions.description_for_field("nonexistent") is None


def test_subclass_override_takes_precedence():
    assert (
        ChildOptions.description_for_field("foo") == "Overridden description for foo."
    )


def test_subclass_own_field_resolved():
    assert ChildOptions.description_for_field("qux") == "Qux on the child only."


def test_inherited_field_resolves_to_parent_docstring():
    # GrandchildOptions doesn't redeclare foo; the description should
    # come from ChildOptions (the nearest ancestor that defines it).
    assert (
        GrandchildOptions.description_for_field("foo")
        == "Overridden description for foo."
    )


def test_class_docstring_is_not_treated_as_field_description():
    # GrandchildOptions has a class docstring but it's not a field doc.
    # Looking up the first real field should still work.
    assert (
        GrandchildOptions.description_for_field("new_field")
        == "A field defined only here."
    )


def test_description_cache_is_populated_per_class():
    """
    The first call should populate a per-class cache.
    """
    # Trigger a lookup
    DescribedOptions.description_for_field("foo")
    # Cache attribute is set on the class's own __dict__ (not inherited).
    assert "_poe_field_descriptions" in DescribedOptions.__dict__


def test_every_taskoptions_field_has_a_description():
    """
    Sanity check that backfill is comprehensive. Lists any field on a
    PoeTask.TaskOptions subclass that lacks a description so gaps are
    discoverable.
    """

    from poethepoet.task.base import PoeTask

    # Walk all registered task types via the name-mangled registry.
    missing: list[tuple[str, str]] = [
        (task_cls.__name__, field_name)
        for task_cls in PoeTask._PoeTask__task_types.values()
        for field_name in task_cls.TaskOptions.get_fields()
        if task_cls.TaskOptions.description_for_field(field_name) is None
    ]

    assert not missing, (
        f"Found {len(missing)} TaskOptions fields without a description: "
        f"{missing!r}. Add a class-attribute docstring immediately after "
        "the annotation."
    )


def test_every_configoptions_field_has_a_description():
    """
    Sanity check for the root ConfigOptions on ProjectConfig.
    """

    from poethepoet.config.partition import ProjectConfig

    missing: list[str] = [
        field_name
        for field_name in ProjectConfig.ConfigOptions.get_fields()
        if ProjectConfig.ConfigOptions.description_for_field(field_name) is None
    ]

    assert not missing, (
        f"Found ProjectConfig.ConfigOptions fields without a description: "
        f"{missing!r}. Add a class-attribute docstring."
    )


def test_every_executoroptions_field_has_a_description():
    """
    Sanity check for ExecutorOptions on every registered PoeExecutor.
    """

    from poethepoet.executor.base import PoeExecutor

    missing: list[tuple[str, str]] = [
        (executor_cls.__name__, field_name)
        for executor_cls in PoeExecutor._PoeExecutor__executor_types.values()
        for field_name in executor_cls.ExecutorOptions.get_fields()
        if executor_cls.ExecutorOptions.description_for_field(field_name) is None
    ]

    assert not missing, (
        f"Found {len(missing)} ExecutorOptions fields without a description: "
        f"{missing!r}. Add a class-attribute docstring immediately after "
        "the annotation."
    )


def test_every_argspec_and_secondary_config_field_has_a_description():
    """
    Sanity check for ArgSpec and the non-primary ConfigOptions classes
    (IncludedConfig and PackagedConfig).
    """

    from poethepoet.config.partition import IncludedConfig, PackagedConfig
    from poethepoet.task.args import ArgSpec

    classes_to_check = (
        ArgSpec,
        IncludedConfig.ConfigOptions,
        PackagedConfig.ConfigOptions,
    )
    missing: list[tuple[str, str]] = [
        (cls.__name__, field_name)
        for cls in classes_to_check
        for field_name in cls.get_fields()
        if cls.description_for_field(field_name) is None
    ]

    assert not missing, (
        f"Found {len(missing)} fields without a description: {missing!r}. "
        "Add a class-attribute docstring immediately after the annotation."
    )


def test_every_typeddict_field_has_a_description():
    """
    Sanity check for the TypedDict option shapes used in the schema. These
    aren't PoeOptions subclasses, so they go through
    extract_field_descriptions directly rather than the
    PoeOptions.description_for_field helper.
    """

    from poethepoet.config.partition import IncludeItem, IncludeScriptItem, TaskGroup
    from poethepoet.config.primitives import EnvDefault, EnvfileOption
    from poethepoet.options._docstrings import extract_field_descriptions

    typed_dicts = (
        IncludeItem,
        IncludeScriptItem,
        TaskGroup,
        EnvDefault,
        EnvfileOption,
    )
    missing: list[tuple[str, str]] = []
    for typed_dict in typed_dicts:
        descriptions = extract_field_descriptions(typed_dict)
        missing.extend(
            (typed_dict.__name__, field_name)
            for field_name in typed_dict.__annotations__
            if field_name not in descriptions
        )

    assert not missing, (
        f"Found {len(missing)} TypedDict fields without a description: "
        f"{missing!r}. Add a class-attribute docstring immediately after "
        "the annotation."
    )
