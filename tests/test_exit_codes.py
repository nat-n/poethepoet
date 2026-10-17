import errno
import sys

import pytest

from poethepoet.app import _is_broken_pipe

_TASKS = """
[tool.poe.tasks]
ok = "poe_test_echo ok"
fail_2 = "poe_test_fail 0 2"
fail_3 = "poe_test_fail 0 3"
# poe_test_fail takes a delay in milliseconds and then an exit code
slow = "poe_test_fail 20000 9"
slow_fail_2 = "poe_test_fail 5000 2"
later_fail_2 = "poe_test_fail 200 2"
bad_glob = { cmd = "poe_test_echo *.nomatch", empty_glob = "fail" }

seq = ["ok", "fail_3", "fail_2"]
seq_nested = ["ok", "seq"]
seq_ignored = { sequence = ["fail_2", "fail_3"], ignore_fail = true }
seq_no_process = ["bad_glob", "fail_3"]

par = { parallel = ["ok", "fail_3"] }
par_killed_sibling_first = { parallel = ["slow", "fail_3"] }
par_slower_failure_first = { parallel = ["slow_fail_2", "fail_3"] }

ref_seq = { ref = "seq" }
with_failed_dep = { cmd = "poe_test_echo sink", deps = ["fail_3"] }
with_failed_seq_dep = { cmd = "poe_test_echo sink", deps = ["seq"] }
with_failed_uses = { cmd = "poe_test_echo sink", uses = { VALUE = "fail_3" } }
ref_with_failed_dep = { ref = "with_failed_dep" }

[tool.poe.tasks.seq_return_non_zero]
sequence = ["fail_2", "fail_3"]
ignore_fail = "return_non_zero"

[tool.poe.tasks.par_return_non_zero]
parallel = ["later_fail_2", "fail_3"]
ignore_fail = "return_non_zero"

[tool.poe.tasks.switch_seq]
control.expr = "'a'"
switch = [{ case = "a", sequence = ["fail_3", "ok"] }]

[tool.poe.tasks.switch_par]
control.expr = "'a'"
switch = [{ case = "a", parallel = ["slow", "fail_3"] }]

[tool.poe.tasks.switch_failed_control]
control.cmd = "poe_test_fail 0 3"
switch = [{ case = "a", cmd = "poe_test_echo case" }]
"""


@pytest.mark.parametrize(
    ("task_name", "expected_code"),
    [
        # A sequence stops at the first failed subtask and exits with its code
        ("seq", 3),
        ("seq_nested", 3),
        ("ref_seq", 3),
        ("switch_seq", 3),
        # If every subtask is run, the code of the first one to fail is still used
        ("seq_return_non_zero", 2),
        ("par_return_non_zero", 3),
        ("seq_ignored", 0),
        # A subtask that fails without running a process has no code to report
        ("seq_no_process", 1),
        # Siblings that poe kills because of a failure are not the failure
        ("par", 3),
        ("par_killed_sibling_first", 3),
        ("par_slower_failure_first", 3),
        ("switch_par", 3),
        # Upstream tasks and control tasks
        ("with_failed_dep", 3),
        ("with_failed_seq_dep", 3),
        ("with_failed_uses", 3),
        ("ref_with_failed_dep", 3),
        ("switch_failed_control", 3),
    ],
)
def test_failed_subtask_exit_code_is_propagated(
    temp_pyproject, run_poe_subproc, task_name, expected_code
):
    """
    A task that fails because one of its subtasks failed exits with the code of the
    first failed subtask, or 1 if it has none
    """
    project_path = temp_pyproject(_TASKS)
    result = run_poe_subproc(task_name, cwd=project_path)
    assert result.code == expected_code, result.capture
    assert "sink" not in result.stdout


@pytest.mark.parametrize(
    ("platform", "error", "is_broken_pipe"),
    [
        ("linux", BrokenPipeError(errno.EPIPE, "Broken pipe"), True),
        ("linux", OSError(errno.EINVAL, "Invalid argument"), False),
        ("win32", OSError(errno.EINVAL, "Invalid argument"), True),
        # e.g. from opening a capture_stdout file with an invalid name
        ("win32", OSError(errno.EINVAL, "Invalid argument", "out?.txt"), False),
    ],
)
def test_only_errors_writing_to_a_closed_pipe_count_as_broken_pipes(
    monkeypatch, platform, error, is_broken_pipe
):
    monkeypatch.setattr(sys, "platform", platform)
    assert _is_broken_pipe(error) == is_broken_pipe
