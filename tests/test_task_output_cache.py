import pytest

from poethepoet.context import TaskOutputCache
from poethepoet.exceptions import ExecutionError


def test_missing_task_output_raises_execution_error():
    with pytest.raises(
        ExecutionError, match="No captured output available for task 'x'"
    ):
        TaskOutputCache().get_task_output(("x",))
