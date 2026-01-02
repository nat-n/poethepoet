import os
import signal
import sys
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
    # Use forward slashes for Windows compatibility in the command string
    pid_file_str = str(pid_file).replace("\\", "/")
    project_path = temp_pyproject(
        f"""
        [tool.poe.tasks.hang]
        cmd = "poe_test_delayed_echo_with_pidfile 60000 'done' '{pid_file_str}'"
        """
    )

    poe_handle = run_poe_subproc_handle("hang", cwd=str(project_path))

    # Wait for child to start and write its PID
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        # Check if poe exited early (indicates task failure)
        if poe_handle.process.poll() is not None:
            stdout, stderr = poe_handle.process.communicate()
            pytest.fail(
                f"Poe exited early (code {poe_handle.process.returncode})\n"
                f"pid_file_str: {pid_file_str}\n"
                f"stdout: {stdout.decode(errors='replace')}\n"
                f"stderr: {stderr.decode(errors='replace')}"
            )
        if pid_file.exists() and pid_file.stat().st_size > 0:
            break
        time.sleep(0.1)
    else:
        # Timeout - gather debug info
        poll_result = poe_handle.process.poll()
        stdout, stderr = b"", b""
        if poll_result is not None:
            stdout, stderr = poe_handle.process.communicate()
        pytest.fail(
            f"Child process did not write PID file in time\n"
            f"pid_file_str: {pid_file_str}\n"
            f"pid_file exists: {pid_file.exists()}\n"
            f"poe poll(): {poll_result}\n"
            f"stdout: {stdout.decode(errors='replace')}\n"
            f"stderr: {stderr.decode(errors='replace')}"
        )

    child_pid = int(pid_file.read_text())

    yield poe_handle, child_pid

    # Cleanup: ensure processes are dead
    if poe_handle.process.poll() is None:
        poe_handle.process.kill()
        poe_handle.process.wait()


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows does not have usable signals for this test"
)
def test_interrupt_terminates_task_and_children(long_running_task):
    """Interrupt signal to poe should terminate both poe and its child processes."""
    poe_handle, child_pid = long_running_task

    # Verify both processes are running
    assert poe_handle.process.poll() is None, "poe should be running"
    assert _pid_exists(child_pid), "child should be running"

    poe_handle.process.send_signal(signal.SIGINT)

    # Both should exit
    assert _wait_for_proc_exit(poe_handle.process), "poe should exit after interrupt"
    poe_handle.process.wait()  # Reap zombie
    assert _wait_for_pid_exit(child_pid), "child should exit after interrupt"


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
