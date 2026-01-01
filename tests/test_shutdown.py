import os
import signal
import time

import pytest


def _wait_for_proc_exit(proc, timeout: float = 5.0) -> bool:
    """Wait for a Popen process to exit, return True if it exited."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return True
        time.sleep(0.1)
    return False


def _wait_for_pid_exit(pid: int, timeout: float = 5.0) -> bool:
    """Wait for a PID to no longer exist, return True if it exited."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


def _pid_exists(pid: int) -> bool:
    """Check if a PID exists in the process table."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


@pytest.fixture
def long_running_task(run_poe_subproc_handle, temp_pyproject, tmp_path):
    """Fixture that starts a long-running poe task and returns handles to check."""
    pid_file = tmp_path / "child.pid"
    project_path = temp_pyproject(
        f"""
        [tool.poe.tasks.hang]
        cmd = "poe_test_delayed_echo_with_pidfile 60000 'done' '{pid_file}'"
        """
    )

    poe_handle = run_poe_subproc_handle("hang", cwd=str(project_path))

    # Wait for child to start and write its PID
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if pid_file.exists() and pid_file.stat().st_size > 0:
            break
        time.sleep(0.1)
    else:
        pytest.fail("Child process did not write PID file in time")

    child_pid = int(pid_file.read_text())

    yield poe_handle, child_pid

    # Cleanup: ensure processes are dead
    if poe_handle.process.poll() is None:
        poe_handle.process.kill()
        poe_handle.process.wait()


@pytest.mark.skipif(not hasattr(signal, "SIGINT"), reason="SIGINT not available")
def test_sigint_terminates_task_and_children(long_running_task):
    """SIGINT to poe should terminate both poe and its child processes."""
    poe_handle, child_pid = long_running_task

    # Verify both processes are running
    assert poe_handle.process.poll() is None, "poe should be running"
    assert _pid_exists(child_pid), "child should be running"

    # Send SIGINT
    poe_handle.process.send_signal(signal.SIGINT)

    # Both should exit
    assert _wait_for_proc_exit(poe_handle.process), "poe should exit after SIGINT"
    poe_handle.process.wait()  # Reap zombie
    assert _wait_for_pid_exit(child_pid), "child should exit after SIGINT"


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="SIGHUP not available")
def test_sighup_terminates_task_and_children(long_running_task):
    """SIGHUP to poe should propagate to children and trigger shutdown."""
    poe_handle, child_pid = long_running_task

    # Verify both processes are running
    assert poe_handle.process.poll() is None, "poe should be running"
    assert _pid_exists(child_pid), "child should be running"

    # Send SIGHUP
    poe_handle.process.send_signal(signal.SIGHUP)

    # Both should exit (SIGHUP propagates to children and triggers shutdown)
    assert _wait_for_proc_exit(poe_handle.process), "poe should exit after SIGHUP"
    poe_handle.process.wait()  # Reap zombie
    assert _wait_for_pid_exit(child_pid), "child should exit after SIGHUP"
