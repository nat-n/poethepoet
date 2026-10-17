import asyncio
import os
import signal
import sys
import time
from typing import Any, cast

import pytest

from poethepoet.io import PoeIO
from poethepoet.shutdown import ShutdownManager, signal_shutdown, stop_process


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
def shutdown_manager():
    loop = asyncio.new_event_loop()
    yield ShutdownManager(loop, PoeIO(make_default=False))
    loop.close()


def test_shutdown_escalates_from_interrupting_to_terminating_to_killing(
    shutdown_manager, fake_poe_process
):
    process = fake_poe_process(stops_on="never")
    shutdown_manager.processes.add(process)

    for urgency in range(1, 5):
        shutdown_manager._urgency = urgency
        shutdown_manager._shutdown()

    assert process.stop_requests == ["interrupt", "interrupt", "terminate", "kill"]
    assert not shutdown_manager.processes


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stops_on", "expected_requests"),
    [
        ("interrupt", ["interrupt"]),
        ("terminate", ["interrupt", "interrupt", "terminate"]),
        ("kill", ["interrupt", "interrupt", "terminate", "kill"]),
    ],
)
async def test_stop_process_escalates_like_ctrl_c_until_it_exits(
    fake_poe_process, stops_on, expected_requests
):
    process = fake_poe_process(stops_on=stops_on)
    await stop_process(process, escalation_interval_s=0.01)
    assert process.stop_requests == expected_requests
    assert process.returncode is not None


@pytest.mark.asyncio
async def test_stop_process_continues_an_escalation_already_in_progress(
    fake_poe_process,
):
    # e.g. a subtask aborted after ctrl+c was pressed is not sent a second interrupt
    # straight away, which a process may take as a request to skip a graceful exit
    process = fake_poe_process(stops_on="terminate")
    signal_shutdown(process, 1)
    await stop_process(process, escalation_interval_s=0.01)
    assert process.stop_requests == ["interrupt", "interrupt", "terminate"]


def test_signal_shutdown_skips_processes_that_have_exited(fake_poe_process):
    process = fake_poe_process(0)
    signal_shutdown(process, 4)
    assert process.stop_requests == []


@pytest.fixture
def long_running_task(run_poe_subproc_handle, temp_pyproject, tmp_path):
    """Fixture that starts a long-running poe task and returns handles to check."""
    pid_file = tmp_path / "child.pid"
    # Use forward slashes for Windows compatibility in the command string
    pid_file_str = str(pid_file).replace("\\", "/")
    project_path = temp_pyproject(f"""
        [tool.poe.tasks.hang]
        cmd = "poe_test_delayed_echo_with_pidfile 60000 'done' '{pid_file_str}'"
        """)

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
    poe_handle.process.send_signal(cast("Any", signal).SIGHUP)

    # Both should exit (SIGHUP propagates to children and triggers shutdown)
    assert _wait_for_proc_exit(poe_handle.process), "poe should exit after SIGHUP"
    poe_handle.process.wait()  # Reap zombie
    assert _wait_for_pid_exit(child_pid), "child should exit after SIGHUP"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_task_killed_by_signal_exits_with_128_plus_signum(run_poe, temp_pyproject):
    project_path = temp_pyproject("""
        [tool.poe.tasks.selfkill]
        shell = "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"
        interpreter = "python"
        """)
    result = run_poe("selfkill", cwd=project_path)
    assert result.code == 128 + signal.SIGTERM


@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_parallel_abort_stops_processes_started_by_subtasks(
    run_poe_subproc, temp_pyproject, tmp_path, delay_factor
):
    """
    Aborting a parallel task also stops processes started by its subtasks, which
    would otherwise keep running, holding the subtask's output open so that poe waits
    for them to exit.
    """
    pid_file = tmp_path / "grandchild.pid"
    # Use forward slashes for Windows compatibility in the command string
    pid_file_str = str(pid_file).replace("\\", "/")
    project_path = temp_pyproject(f"""
        [tool.poe.tasks.spawner]
        interpreter = "python"
        shell = '''
        import subprocess, sys, time
        grandchild = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"]
        )
        with open("{pid_file_str}", "w") as pid_file:
            pid_file.write(str(grandchild.pid))
        print("started", flush=True)
        time.sleep(60)
        '''

        [tool.poe.tasks.aborted]
        parallel = ["spawner", {{ cmd = "poe_test_fail {1000 * delay_factor} 3" }}]
        """)

    start_time = time.monotonic()
    result = run_poe_subproc("aborted", cwd=project_path, timeout=60)

    assert result.code == 3
    assert result.stdout == "spawner | started\n"
    # Far less than the grandchild would take to exit by itself
    assert time.monotonic() - start_time < 30
    if sys.platform != "win32":
        assert _wait_for_pid_exit(int(pid_file.read_text())), "grandchild should exit"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal handlers")
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_parallel_abort_interrupts_subtasks_like_ctrl_c(
    run_poe_subproc, temp_pyproject, tmp_path, delay_factor
):
    """
    Subtasks stopped by an abort are interrupted as by ctrl+c, giving them a chance
    to exit gracefully, and are interrupted only once.
    """
    log_file = tmp_path / "interrupts.log"
    project_path = temp_pyproject(f"""
        [tool.poe.tasks.graceful]
        interpreter = "python"
        shell = '''
        import signal, sys, time
        def on_interrupt(signum, frame):
            with open("{log_file}", "a") as log:
                log.write("interrupted\\n")
            sys.exit(130)
        signal.signal(signal.SIGINT, on_interrupt)
        print("ready", flush=True)
        time.sleep(60)
        '''

        [tool.poe.tasks.aborted]
        parallel = ["graceful", {{ cmd = "poe_test_fail {1000 * delay_factor} 3" }}]
        """)

    result = run_poe_subproc("aborted", cwd=project_path, timeout=30)

    assert result.code == 3
    assert log_file.read_text() == "interrupted\n"
