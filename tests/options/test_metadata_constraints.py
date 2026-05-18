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
