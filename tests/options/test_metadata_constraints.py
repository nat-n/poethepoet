"""
Tests for Metadata-driven runtime constraints on PoeOptions fields.
"""

from collections.abc import Sequence
from typing import Annotated

import pytest

from poethepoet.exceptions import ConfigValidationError
from poethepoet.options.annotations import (
    ListType,
    Metadata,
    PrimitiveType,
    TypeAnnotation,
    UnionType,
)
from poethepoet.options.base import PoeOptions


def test_module_imports() -> None:
    assert Metadata is not None


def test_empty_interpreter_list_rejected():
    """
    Verify that an empty list passed as the shell interpreter option is rejected.
    Tracks the regression introduced when the bespoke validate() override was
    removed; restored declaratively via Metadata(min_items=1) on the list branch.
    """
    from poethepoet.task.shell import ShellTask

    with pytest.raises(ConfigValidationError):
        list(ShellTask.TaskOptions.parse({"interpreter": []}))


class PatternedOptions(PoeOptions):
    name: Annotated[str, Metadata(pattern=r"^[a-z]+$")]


def test_pattern_accepts_matching_value():
    options = next(PatternedOptions.parse({"name": "hello"}))
    assert options.get("name") == "hello"


def test_pattern_rejects_non_matching_value():
    with pytest.raises(ConfigValidationError) as exc_info:
        list(PatternedOptions.parse({"name": "Hello"}))
    # Error message must name the field and quote the pattern
    msg = str(exc_info.value)
    assert "name" in msg
    assert "^[a-z]+$" in msg


def test_pattern_uses_unanchored_search():
    """
    JSON Schema 'pattern' semantics are unanchored (re.search), so a
    pattern without ^/$ should match if the substring appears anywhere.
    """

    class SubstringPatternOptions(PoeOptions):
        token: Annotated[str, Metadata(pattern=r"[0-9]+")]

    options = next(SubstringPatternOptions.parse({"token": "abc123def"}))
    assert options.get("token") == "abc123def"

    with pytest.raises(ConfigValidationError):
        list(SubstringPatternOptions.parse({"token": "no digits here"}))


def test_pattern_not_checked_when_type_is_wrong():
    """
    If the value isn't a string, the pattern check is skipped (type
    error is reported instead).
    """
    with pytest.raises(ConfigValidationError) as exc_info:
        list(PatternedOptions.parse({"name": 123}))
    msg = str(exc_info.value)
    assert "str" in msg or "string" in msg  # type error, not pattern error


def test_metadata_get_returns_falsy_value():
    """
    metadata_get must distinguish 'unset' from 'set to a falsy value'.
    Returns the actual stored value (including 0, False, '') rather than
    the default when the attribute is set.
    """

    # Use Metadata.config_name with an empty string to exercise the falsy-but-set case.
    class ConfigNamedOptions(PoeOptions):
        foo: Annotated[str, Metadata(config_name="")] = ""

    annotation = ConfigNamedOptions.get_fields()["foo"]
    # Truthiness-based metadata_get would return None for the empty config_name.
    # Correct semantics: return "" because config_name was explicitly set.
    assert annotation.metadata_get("config_name") == ""


def test_pattern_silently_ignored_on_non_str_annotation():
    """
    Metadata(pattern=...) applies only to str fields. Attaching it to an
    int annotation is a no-op (the pattern is not checked, the int value is
    accepted as long as it has the right type).
    """

    class IntWithPatternOptions(PoeOptions):
        count: Annotated[int, Metadata(pattern=r"[0-9]+")] = 0

    # Pattern is ignored; int values pass through unchecked by pattern.
    options = next(IntWithPatternOptions.parse({"count": 42}))
    assert options.get("count") == 42

    # The standard type check still fires for wrong types.
    with pytest.raises(ConfigValidationError):
        list(IntWithPatternOptions.parse({"count": "not an int"}))


def test_examples_stored_on_metadata():
    """examples is documentation-only — no runtime validation, just preserved
    for downstream consumers (the schema generator).
    """

    class ExampledOptions(PoeOptions):
        path: Annotated[
            str, Metadata(examples=["output.log", "${POE_PWD}/output.txt"])
        ] = ""

    # Should parse without complaint.
    options = next(ExampledOptions.parse({"path": "anything"}))
    assert options.get("path") == "anything"

    # The Metadata object is accessible through the field's TypeAnnotation:
    annotation = ExampledOptions.get_fields()["path"]
    examples = annotation.metadata_get("examples")
    assert examples == ["output.log", "${POE_PWD}/output.txt"]


class BoundedIntOptions(PoeOptions):
    count: Annotated[int, Metadata(minimum=0, maximum=100)] = 0


def test_minimum_accepts_value_at_bound():
    options = next(BoundedIntOptions.parse({"count": 0}))
    assert options.get("count") == 0


def test_minimum_rejects_value_below_bound():
    with pytest.raises(ConfigValidationError) as exc_info:
        list(BoundedIntOptions.parse({"count": -1}))
    msg = str(exc_info.value)
    assert "count" in msg
    assert "0" in msg  # the bound


def test_maximum_accepts_value_at_bound():
    options = next(BoundedIntOptions.parse({"count": 100}))
    assert options.get("count") == 100


def test_maximum_rejects_value_above_bound():
    with pytest.raises(ConfigValidationError) as exc_info:
        list(BoundedIntOptions.parse({"count": 101}))
    msg = str(exc_info.value)
    assert "count" in msg
    assert "100" in msg


def test_bounds_apply_to_floats():
    class BoundedFloatOptions(PoeOptions):
        ratio: Annotated[float, Metadata(minimum=0.0, maximum=1.0)] = 0.5

    next(BoundedFloatOptions.parse({"ratio": 0.5}))  # in range
    next(BoundedFloatOptions.parse({"ratio": 0.0}))  # at minimum
    next(BoundedFloatOptions.parse({"ratio": 1.0}))  # at maximum
    with pytest.raises(ConfigValidationError):
        list(BoundedFloatOptions.parse({"ratio": 1.1}))


def test_bounds_not_applied_to_strings():
    """
    minimum/maximum apply only to numeric types; on a str field they're
    silently ignored (the schema generator would also skip them).
    """

    class StringWithBoundsOptions(PoeOptions):
        # Intentionally weird combination - runtime should not crash.
        text: Annotated[str, Metadata(minimum=0, maximum=100)] = ""

    options = next(StringWithBoundsOptions.parse({"text": "hello"}))
    assert options.get("text") == "hello"


def test_minimum_zero_is_enforced():
    """
    Regression test for the T4.5 metadata_get fix: minimum=0 must NOT
    be silently dropped (which would happen with the old truthiness check).
    """

    class ZeroMinOptions(PoeOptions):
        count: Annotated[int, Metadata(minimum=0)] = 0

    # Zero is allowed (at the bound)
    next(ZeroMinOptions.parse({"count": 0}))
    # Negative is rejected
    with pytest.raises(ConfigValidationError):
        list(ZeroMinOptions.parse({"count": -1}))


def test_min_length_rejects_short_string():
    class MinLenStrOptions(PoeOptions):
        name: Annotated[str, Metadata(min_length=3)] = ""

    next(MinLenStrOptions.parse({"name": "abc"}))  # at boundary
    next(MinLenStrOptions.parse({"name": "abcd"}))  # above
    with pytest.raises(ConfigValidationError) as exc_info:
        list(MinLenStrOptions.parse({"name": "ab"}))
    assert "name" in str(exc_info.value)
    assert "3" in str(exc_info.value)


def test_max_length_rejects_long_string():
    class MaxLenStrOptions(PoeOptions):
        name: Annotated[str, Metadata(max_length=5)] = ""

    next(MaxLenStrOptions.parse({"name": "hello"}))  # at boundary
    with pytest.raises(ConfigValidationError):
        list(MaxLenStrOptions.parse({"name": "helloX"}))


def test_length_zero_bounds_are_enforced() -> None:
    """
    Regression for the metadata_get falsy-value fix applied to string length
    bounds: min_length=0 and max_length=0 must NOT be silently dropped
    (which would happen with a naive truthiness check).
    """

    class ZeroMaxStrOptions(PoeOptions):
        name: Annotated[str, Metadata(max_length=0)] = ""

    # Empty string is allowed (at the bound)
    next(ZeroMaxStrOptions.parse({"name": ""}))
    # Any non-empty string exceeds max_length=0 and is rejected
    with pytest.raises(ConfigValidationError):
        list(ZeroMaxStrOptions.parse({"name": "x"}))


def test_items_zero_bounds_are_enforced() -> None:
    """
    Regression for the metadata_get falsy-value fix applied to list item
    bounds: min_items=0 and max_items=0 must NOT be silently dropped
    (which would happen with a naive truthiness check).
    """

    class ZeroMinListOptions(PoeOptions):
        items: Annotated[Sequence[str], Metadata(min_items=0)] = ()

    # min_items=0 allows the empty list (it's set, just to its lowest bound)
    next(ZeroMinListOptions.parse({"items": []}))
    next(ZeroMinListOptions.parse({"items": ["a"]}))

    class ZeroMaxListOptions(PoeOptions):
        items: Annotated[Sequence[str], Metadata(max_items=0)] = ()

    # max_items=0 allows only the empty list
    next(ZeroMaxListOptions.parse({"items": []}))
    with pytest.raises(ConfigValidationError):
        list(ZeroMaxListOptions.parse({"items": ["a"]}))


def test_annotated_nests_inside_union_branch_is_parsed() -> None:
    """
    Union-of-Annotated parses to a UnionType whose specific branch carries
    the inner Metadata.
    """

    parsed = TypeAnnotation.parse(
        str | Annotated[Sequence[str], Metadata(min_items=1)] | None
    )
    assert isinstance(parsed, UnionType)

    list_branch = next(vt for vt in parsed._value_types if isinstance(vt, ListType))
    assert list_branch.metadata_get("min_items") == 1

    str_branch = next(vt for vt in parsed._value_types if isinstance(vt, PrimitiveType))
    assert str_branch._metadata is None


def test_union_does_not_propagate_metadata_to_children() -> None:
    """
    Metadata attached at Annotated[Union[...], Metadata(...)] stays on the
    UnionType — it is NOT copied into child TypeAnnotations, regardless of
    whether the metadata is field-level (config_name) or type-level (min_items).
    A regression that special-cased one scope but not the other would slip
    past a single-scope check.
    """

    field_level = TypeAnnotation.parse(
        Annotated[str | int, Metadata(config_name="foo")]
    )
    assert isinstance(field_level, UnionType)
    assert field_level.metadata_get("config_name") == "foo"
    for branch in field_level._value_types:
        assert branch._metadata is None

    type_level = TypeAnnotation.parse(
        Annotated[str | Sequence[str], Metadata(min_items=1)]
    )
    assert isinstance(type_level, UnionType)
    assert type_level.metadata_get("min_items") == 1
    for branch in type_level._value_types:
        assert branch._metadata is None
    # Consequently, the list branch reads no min_items at validation time.
    list_branch = next(
        vt for vt in type_level._value_types if isinstance(vt, ListType)
    )
    assert list_branch.metadata_get("min_items") is None


def test_union_str_or_list_with_min_items_on_list_branch() -> None:
    """
    The motivating example: `min_items=1` lives on the list branch and
    rejects empty lists, but the string branch is unaffected.
    """

    class StrOrListOpt(PoeOptions):
        value: str | Annotated[Sequence[str], Metadata(min_items=1)] | None = None

    # String branch — any string OK (even empty).
    options = next(StrOrListOpt.parse({"value": ""}))
    assert options.get("value") == ""

    # List branch with items — OK.
    options = next(StrOrListOpt.parse({"value": ["a"]}))
    assert options.get("value") == ["a"]

    # List branch empty — rejected.
    with pytest.raises(ConfigValidationError):
        list(StrOrListOpt.parse({"value": []}))

    # Pin behavior, not coincidence: the string branch carries no metadata,
    # so the runtime can't conflate it with the list branch's constraint.
    parsed = StrOrListOpt.get_fields()["value"]
    assert isinstance(parsed, UnionType)
    str_branch = next(
        vt for vt in parsed._value_types if isinstance(vt, PrimitiveType)
    )
    assert str_branch.metadata_get("min_items") is None


def test_min_items_rejects_short_list() -> None:
    """
    min_items enforces a minimum number of elements for list/sequence fields.
    """

    class MinItemsOpt(PoeOptions):
        items: Annotated[Sequence[str], Metadata(min_items=2)] = ()

    next(MinItemsOpt.parse({"items": ["a", "b"]}))  # at boundary
    with pytest.raises(ConfigValidationError) as exc_info:
        list(MinItemsOpt.parse({"items": ["a"]}))
    assert "items" in str(exc_info.value)
    assert "2" in str(exc_info.value)


def test_max_items_rejects_long_list() -> None:
    """
    max_items enforces a maximum number of elements for list/sequence fields.
    """

    class MaxItemsOpt(PoeOptions):
        items: Annotated[Sequence[str], Metadata(max_items=2)] = ()

    next(MaxItemsOpt.parse({"items": ["a", "b"]}))  # at boundary
    with pytest.raises(ConfigValidationError) as exc_info:
        list(MaxItemsOpt.parse({"items": ["a", "b", "c"]}))
    msg = str(exc_info.value)
    assert "items" in msg
    assert "2" in msg  # the max bound
    assert "3" in msg  # the actual offending length


def test_min_length_does_not_apply_to_lists() -> None:
    """
    min_length is exclusively a string constraint. Attaching it to a list
    field has no effect at runtime — the schema generator raises on this
    mismatch at build time (runtime silently ignores it, the permissive contract).
    """

    class MinLengthOnListOpt(PoeOptions):
        items: Annotated[Sequence[str], Metadata(min_length=99)] = ()

    # Empty list passes; min_length is ignored on lists.
    options = next(MinLengthOnListOpt.parse({"items": []}))
    assert options.get("items") == []


def test_type_level_metadata_on_outer_union_is_silently_ignored() -> None:
    """
    A type-level constraint attached to the outer Annotated[Union[...]]
    is not propagated to child branches, so the runtime never enforces it.
    The schema generator surfaces this as an error at build time — at
    runtime it is silently a no-op (the permissive contract from the spec).
    """

    class OuterMetadataOpt(PoeOptions):
        value: Annotated[str | Sequence[str], Metadata(min_items=1)] = ""

    # Empty list passes — min_items=1 on the outer union does not constrain.
    options = next(OuterMetadataOpt.parse({"value": []}))
    assert options.get("value") == []


def test_interpreter_single_string_accepted() -> None:
    """A single Literal-matching interpreter string parses cleanly."""
    from poethepoet.task.shell import ShellTask

    parsed = next(ShellTask.TaskOptions.parse({"interpreter": "bash"}))
    assert parsed.get("interpreter") == "bash"


def test_interpreter_list_of_strings_accepted() -> None:
    """A non-empty list of Literal-matching strings parses cleanly."""
    from poethepoet.task.shell import ShellTask

    parsed = next(ShellTask.TaskOptions.parse({"interpreter": ["bash", "sh"]}))
    assert list(parsed.get("interpreter")) == ["bash", "sh"]


def test_interpreter_none_accepted() -> None:
    """The None branch of the union is honored (interpreter is optional)."""
    from poethepoet.task.shell import ShellTask

    parsed = next(ShellTask.TaskOptions.parse({"interpreter": None}))
    assert parsed.get("interpreter") is None


def test_interpreter_unknown_string_rejected() -> None:
    """LiteralType still enforces membership after the refactor."""
    from poethepoet.task.shell import ShellTask

    with pytest.raises(ConfigValidationError):
        list(ShellTask.TaskOptions.parse({"interpreter": "not_a_real_shell"}))


def test_metadata_type_constraints_table() -> None:
    """
    Schema generator needs to know which constraints apply to which types.
    Field-level metadata (config_name, examples) is NOT in this table.
    """

    constraints = Metadata.type_constraints()
    assert constraints["pattern"] == frozenset({"string"})
    assert constraints["min_length"] == frozenset({"string"})
    assert constraints["max_length"] == frozenset({"string"})
    assert constraints["minimum"] == frozenset({"integer", "number"})
    assert constraints["maximum"] == frozenset({"integer", "number"})
    assert constraints["min_items"] == frozenset({"array"})
    assert constraints["max_items"] == frozenset({"array"})
    assert "config_name" not in constraints
    assert "examples" not in constraints
