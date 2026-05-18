"""
Tests for Metadata-driven runtime constraints on PoeOptions fields.
"""

import pytest

from poethepoet.exceptions import ConfigValidationError
from poethepoet.options.annotations import Metadata


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
