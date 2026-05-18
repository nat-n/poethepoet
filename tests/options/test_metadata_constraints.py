"""
Tests for Metadata-driven runtime constraints on PoeOptions fields.
"""

from typing import Annotated

import pytest

from poethepoet.exceptions import ConfigValidationError
from poethepoet.options.annotations import Metadata
from poethepoet.options.base import PoeOptions


# Placeholder import sentinel: this module is intentionally minimal until
# Tasks 4-7 add the corresponding Metadata fields.
def test_module_imports():
    assert Metadata is not None


@pytest.mark.xfail(
    reason=(
        "Empty-list rejection for shell interpreter not yet restored;"
        " see Task 7 (min_length Metadata addition)"
    )
)
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
