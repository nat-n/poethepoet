from typing import Annotated, Any, TypedDict

import pytest

from poethepoet.exceptions import ConfigValidationError
from poethepoet.options import PoeOptions
from poethepoet.options.annotations import Metadata


class EnvDefault(TypedDict):
    default: str


class SamplePoeOptions(PoeOptions):
    foo: str
    bar: int = 42
    baz: bool = False
    qux: list[str] = []
    # annotate as Any to avoid TypeAnnotation parsing of nested PoeOptions
    # provide a default so strict parsing does not require it
    with_: Annotated[Any, Metadata(config_name="with")] = {}
    # provide a sensible default for the TypedDict field
    env: EnvDefault = {"default": ""}


def test_poe_options_basic_parse_and_defaults():
    """Basic parse: provided values are kept; defaults are used when omitted."""
    options = next(
        SamplePoeOptions.parse(
            {
                "foo": "hello",
                "baz": True,
                "qux": ["a", "b", "c"],
            }
        )
    )

    assert options.get("foo") == "hello"
    assert options.get("bar") == 42  # declared default
    assert options.get("baz") is True
    assert options.get("qux") == ["a", "b", "c"]


def test_with_field_accepts_any_and_preserves_value():
    """If a field is annotated as Any, parse preserves the provided value."""
    data = {"foo": "x", "with": {"extra_foo": 2.71}, "env": {"default": "v"}}

    options = next(SamplePoeOptions.parse(data))

    nested_value = options.get("with")
    assert isinstance(nested_value, dict)
    assert nested_value["extra_foo"] == pytest.approx(2.71)


def test_missing_required_raises_strict():
    """In strict mode, missing required keys cause ConfigValidationError."""
    with pytest.raises(ConfigValidationError):
        # missing 'foo'
        list(SamplePoeOptions.parse({"bar": 1, "env": {"default": "v"}}))


def test_unrecognised_option_raises_strict():
    """Unknown options are rejected in strict mode."""
    with pytest.raises(ConfigValidationError):
        list(SamplePoeOptions.parse({"foo": "ok", "env": {"default": "v"}, "bad": 1}))


def test_strict_false_allows_missing_and_get_returns_zero_value():
    """When strict=False, missing required options do not raise, and get() returns
    the zero value (e.g. empty string for str) when nothing provided.
    """
    options = next(SamplePoeOptions.parse({"env": {"default": "v"}}, strict=False))

    # foo was not provided; get() should return the zero value for str
    assert options.get("foo") == ""


def test_access_option_with_keyword_name():
    data = {"foo": "x", "with": {"extra_foo": 9.9}, "env": {"default": "v"}}
    options = next(SamplePoeOptions.parse(data))

    # attribute on the object is with_ (because 'with' is a keyword)
    assert hasattr(options, "with_")
    value = options.with_
    assert isinstance(value, dict)

    # get('with') should resolve to the stored attribute (annotated as Any)
    value = options.get("with")
    assert isinstance(value, dict)

    assert options.with_ is options.get("with")


def test_optional_field_returns_none_when_not_set():
    class OptTest(PoeOptions):
        maybe: int | None

    opt = next(OptTest.parse({}, strict=False))
    assert opt.maybe is None
    assert opt.get("maybe") is None


def test_list_type_validation_error():
    """Supplying wrong type for a list field should raise ConfigValidationError
    with an explanatory message."""
    bad = {"foo": "x", "qux": "not-a-list", "env": {"default": "v"}}
    with pytest.raises(ConfigValidationError) as exc:
        list(SamplePoeOptions.parse(bad))

    assert "must be a list" in str(exc.value)


def test_typed_dict_missing_and_unexpected_keys():
    """TypedDict validation should report missing required keys and unexpected keys."""
    # Missing required key 'default'
    bad_missing = {"foo": "x", "env": {}}
    with pytest.raises(ConfigValidationError) as exc_missing:
        list(SamplePoeOptions.parse(bad_missing))
    msg = str(exc_missing.value)
    assert "missing required key" in msg or "missing required" in msg

    # Unexpected extra key in typed dict
    bad_extra = {"foo": "x", "env": {"default": "v", "extra": 1}}
    with pytest.raises(ConfigValidationError) as exc_extra:
        list(SamplePoeOptions.parse(bad_extra))
    assert "contains unexpected key" in str(exc_extra.value)


def test_dash_case_keys_map_to_attributes_and_get():
    """Config keys using dash-case should map to snake_case attributes."""

    class DashOptions(PoeOptions):
        some_field: Annotated[int, Metadata(config_name="some-field")]

    opts = next(DashOptions.parse({"some-field": 7}))
    # attribute stored using snake_case
    assert opts.some_field == 7
    # get() accepts dash-case keys too
    assert opts.get("some-field") == 7
    # also get via snake_case works
    assert opts.get("some_field") == 7


def test_dash_case_key_without_config_name():
    class DashOptions(PoeOptions):
        some_field: int

    opts = next(DashOptions.parse({"some_field": 7}))
    # attribute stored using snake_case
    assert opts.some_field == 7
    # also get via snake_case works
    assert opts.get("some_field") == 7


def test_multiple_underscores_and_dash_case():
    """Multiple underscores inside attribute names are converted to
    dashes in config keys."""

    class MultiUnder(PoeOptions):
        complex_name_field: Annotated[str, Metadata(config_name="complex-name-field")]

    opts = next(MultiUnder.parse({"complex-name-field": "ok"}))
    assert opts.complex_name_field == "ok"
    assert opts.get("complex_name_field") == "ok"
    assert opts.get("complex-name-field") == "ok"


def test_dash_case_zero_value_with_strict_false():
    """When strict=False, get() with dash-case key should return type zero value."""

    class DashZero(PoeOptions):
        missing_field: Annotated[str, Metadata(config_name="missing-field")]

    opts = next(DashZero.parse({}, strict=False))
    assert opts.get("missing-field") == ""


def test_annotation_zero_values_validate():
    """
    Every TypeAnnotation subclass should produce a zero_value that validates against
    its own type definition.
    """
    from typing import Any, Literal, TypedDict

    from poethepoet.options.annotations import TypeAnnotation

    class SimpleTD(TypedDict):
        name: str
        count: int

    annotations = [
        str,
        int,
        float,
        bool,
        dict[str, int],
        list[str],
        tuple[str, ...],
        Literal["a", "b"],
        int | None,
        int | str,
        Any,
        None,
        SimpleTD,
    ]

    from poethepoet.options.annotations import UnionType

    for ann in annotations:
        annotation = TypeAnnotation.parse(ann)
        z = annotation.zero_value()
        errors = list(annotation.validate((), z))
        if errors:
            # If validation failed, allow it only when some union member
            # accepts the zero value (covers optional unions returning None).
            if isinstance(annotation, UnionType):
                for member in annotation._value_types:
                    if not list(member.validate((), z)):
                        break
                else:
                    pytest.fail(
                        f"zero_value for {annotation} produced errors: {errors} "
                        f"(value: {z!r})"
                    )
                continue

            pytest.fail(
                f"zero_value for {annotation} produced errors: {errors} (value: {z!r})"
            )


def test_duplicate_config_names_not_tolerated():
    """Duplicate config key mappings (between attribute and config_name)
    should raise a RuntimeError when resolving field attributes.
    """

    class CollideAttrAndConfig(PoeOptions):
        existing: int
        # This field's config_name collides with attribute 'existing'
        other: Annotated[int, Metadata(config_name="existing")]

    with pytest.raises(RuntimeError):
        CollideAttrAndConfig.get_field_attribute("existing")


def test_duplicate_config_name_between_fields_not_tolerated():
    """Two fields with the same `config_name` should also raise."""

    class CollideConfigNames(PoeOptions):
        a: Annotated[int, Metadata(config_name="dup")]
        b: Annotated[int, Metadata(config_name="dup")]

    with pytest.raises(RuntimeError):
        CollideConfigNames.get_field_attribute("a")


def test_register_type_alias_makes_literal_resolvable_in_annotations():
    """Verify that an alias registered via register_type_alias is findable
    when PoeOptions resolves annotation strings."""

    from typing import Literal

    from poethepoet.options import PoeOptions
    from poethepoet.options.annotations import register_type_alias

    Colour = register_type_alias(  # noqa: N806
        "Colour", Literal["red", "green", "blue"]
    )

    class ColouredOptions(PoeOptions):
        favourite: Colour = "red"

    options = next(ColouredOptions.parse({"favourite": "green"}))
    assert options.get("favourite") == "green"

    with pytest.raises(ConfigValidationError):
        list(ColouredOptions.parse({"favourite": "yellow"}))


def test_group_name_pattern_constant_exposed() -> None:
    """
    Module-level so the schema generator can import it as the single
    source of truth.
    """
    from poethepoet.config.partition import _GROUP_NAME_PATTERN

    assert _GROUP_NAME_PATTERN.fullmatch("my_group")
    assert _GROUP_NAME_PATTERN.fullmatch("my-group")
    assert _GROUP_NAME_PATTERN.fullmatch("group123")
    assert not _GROUP_NAME_PATTERN.fullmatch("bad group")
    assert not _GROUP_NAME_PATTERN.fullmatch("")


def test_group_name_pattern_accepts_unicode_at_runtime() -> None:
    """
    Python's ``\\w`` is Unicode-aware, so the runtime accepts group names
    from any script. The schema's ECMA-262 ``\\w`` is ASCII-only, so
    editor validators end up slightly stricter \u2014 intentional.
    """
    from poethepoet.config.partition import _GROUP_NAME_PATTERN

    assert _GROUP_NAME_PATTERN.fullmatch("\u03b1_group")
    assert _GROUP_NAME_PATTERN.fullmatch("caf\u00e9")
    assert _GROUP_NAME_PATTERN.fullmatch("\u65e5\u672c\u8a9e")


def test_project_config_accepts_unicode_group_name() -> None:
    """
    End-to-end runtime guard: a Unicode-letter group key is accepted by
    ``ProjectConfig.ConfigOptions.parse``.
    """
    from poethepoet.config.partition import ProjectConfig

    config = {
        "tasks": {"hello": "echo hi"},
        "groups": {"\u03b1_group": {"heading": "Greek-named group"}},
    }
    parsed = next(ProjectConfig.ConfigOptions.parse(config, strict=True))
    assert "\u03b1_group" in parsed.get("groups")


def test_task_name_pattern_unified_encompasses_first_char_rule() -> None:
    """
    The regex enforces "letter or underscore first" on its own — no
    separate runtime check needed.
    """
    from poethepoet.task.base import _TASK_NAME_PATTERN

    assert _TASK_NAME_PATTERN.fullmatch("hello")
    assert _TASK_NAME_PATTERN.fullmatch("_private")
    assert _TASK_NAME_PATTERN.fullmatch("Task-1")
    assert _TASK_NAME_PATTERN.fullmatch("name:with:colons")
    assert _TASK_NAME_PATTERN.fullmatch("with+plus")

    assert not _TASK_NAME_PATTERN.fullmatch("1bad")
    assert not _TASK_NAME_PATTERN.fullmatch("-bad")
    assert not _TASK_NAME_PATTERN.fullmatch(" bad")
    assert not _TASK_NAME_PATTERN.fullmatch("")


def test_task_name_pattern_accepts_unicode_first_char() -> None:
    """
    Python's ``\\w`` is Unicode-aware, so a task name can start with a
    letter from any script. The schema's ECMA-262 ``\\w`` collapses
    ``[^\\W\\d]`` to ``[A-Za-z_]`` — schema is the stricter side.
    """
    from poethepoet.task.base import _TASK_NAME_PATTERN

    assert _TASK_NAME_PATTERN.fullmatch("αlpha_task")  # noqa: RUF001
    assert _TASK_NAME_PATTERN.fullmatch("café_run")
    assert _TASK_NAME_PATTERN.fullmatch("日本語")


def test_runtime_accepts_unicode_first_char_task_name() -> None:
    """
    End-to-end guard: TaskSpecFactory validates a Unicode-named task
    without raising.
    """
    from poethepoet.config import PoeConfig
    from poethepoet.task.base import TaskSpecFactory

    config = PoeConfig(
        table={"tasks": {"αlpha_task": {"cmd": "echo hi"}}},  # noqa: RUF001
    )
    factory = TaskSpecFactory(config)
    factory.load_all()

    spec = next(iter(factory))
    spec.validate(config, factory)


def test_runtime_still_rejects_invalid_task_names_via_unified_pattern() -> None:
    """
    Digit-first task names are rejected by the regex itself, with no
    separate ``isalpha()`` check.
    """
    from poethepoet.config import PoeConfig
    from poethepoet.task.base import TaskSpecFactory

    config = PoeConfig(
        table={"tasks": {"1bad_name": {"cmd": "echo hi"}}},
    )
    factory = TaskSpecFactory(config)
    factory.load_all()

    spec = next(iter(factory))
    with pytest.raises(ConfigValidationError):
        spec.validate(config, factory)


def test_poe_task_get_task_class_returns_registered_class() -> None:
    from poethepoet.task.base import PoeTask
    from poethepoet.task.cmd import CmdTask

    assert PoeTask.get_task_class("cmd") is CmdTask


def test_poe_task_get_task_class_raises_for_unknown_key() -> None:
    from poethepoet.task.base import PoeTask

    with pytest.raises(KeyError, match="Unknown task type"):
        PoeTask.get_task_class("not_a_real_task_type")


def test_poe_executor_get_executor_class_returns_registered_class() -> None:
    from poethepoet.executor.base import PoeExecutor
    from poethepoet.executor.poetry import PoetryExecutor

    assert PoeExecutor.get_executor_class("poetry") is PoetryExecutor


def test_poe_executor_get_executor_class_raises_for_unknown_key() -> None:
    from poethepoet.executor.base import PoeExecutor

    with pytest.raises(KeyError, match="Unknown executor type"):
        PoeExecutor.get_executor_class("not_a_real_executor")


def test_poe_executor_get_executor_types_includes_known_keys() -> None:
    from poethepoet.executor.base import PoeExecutor

    keys = set(PoeExecutor.get_executor_types())
    # "auto" is intentionally NOT in the registry.
    for expected in ("poetry", "uv", "virtualenv", "simple"):
        assert expected in keys
    assert "auto" not in keys
