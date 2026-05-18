"""
Tests for Metadata-driven runtime constraints on PoeOptions fields.
"""

from collections.abc import Sequence
from typing import Annotated

import pytest

from poethepoet.exceptions import ConfigValidationError
from poethepoet.options.annotations import Metadata
from poethepoet.options.base import PoeOptions


# Placeholder import sentinel: this module is intentionally minimal until
# Tasks 4-7 add the corresponding Metadata fields.
def test_module_imports():
    assert Metadata is not None


def test_empty_interpreter_list_rejected():
    """
    Verify that an empty list passed as the shell interpreter option is rejected.
    Tracks the regression introduced when the bespoke validate() override was
    removed; Task 7 restores this rule declaratively via Metadata(min_length=1).
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


def test_min_length_rejects_short_list():
    class MinLenListOptions(PoeOptions):
        items: Annotated[Sequence[str], Metadata(min_length=1)] = ()

    next(MinLenListOptions.parse({"items": ["one"]}))  # at boundary
    with pytest.raises(ConfigValidationError) as exc_info:
        list(MinLenListOptions.parse({"items": []}))
    assert "items" in str(exc_info.value)


def test_max_length_rejects_long_list():
    class MaxLenListOptions(PoeOptions):
        items: Annotated[Sequence[str], Metadata(max_length=2)] = ()

    next(MaxLenListOptions.parse({"items": ["a", "b"]}))  # at boundary
    with pytest.raises(ConfigValidationError):
        list(MaxLenListOptions.parse({"items": ["a", "b", "c"]}))


def test_length_zero_bounds_are_enforced():
    """
    Regression test for the T4.5 metadata_get fix applied to the length
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

    class ZeroMinListOptions(PoeOptions):
        items: Annotated[Sequence[str], Metadata(min_length=0)] = ()

    # min_length=0 allows the empty list (it's set, just to its lowest bound)
    next(ZeroMinListOptions.parse({"items": []}))
    next(ZeroMinListOptions.parse({"items": ["a"]}))
