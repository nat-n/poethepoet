import asyncio
import os
import shutil
import signal
import subprocess
import sys
from typing import Any, cast

import pytest

from poethepoet.executor import base as executor_base
from poethepoet.executor.base import PoeProcess


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
@pytest.mark.parametrize(
    ("method", "expected_signal"),
    [("interrupt", "SIGINT"), ("terminate", "SIGTERM"), ("kill", "SIGKILL")],
)
def test_posix_process_stop_signals_its_process_group(
    monkeypatch, fake_subprocess, method, expected_signal
):
    killpg_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        os, "killpg", lambda pgid, sig: killpg_calls.append((pgid, sig))
    )
    process = PoeProcess(cast("Any", fake_subprocess()))

    getattr(process, method)()

    # The subprocess leads its own process group, so the group shares its pid
    assert killpg_calls == [(process.pid, getattr(signal, expected_signal))]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
@pytest.mark.parametrize("error", [ProcessLookupError, PermissionError])
def test_posix_process_stop_tolerates_a_group_that_cannot_be_signalled(
    monkeypatch, fake_subprocess, error
):
    # e.g. macOS raises PermissionError for a group whose processes have all exited
    # but not yet been reaped
    def killpg(pgid: int, sig: int):
        raise error()

    monkeypatch.setattr(os, "killpg", killpg)
    process = PoeProcess(cast("Any", fake_subprocess()))

    process.interrupt()


@pytest.mark.parametrize(
    ("method", "no_console_ctrl", "expected_taskkill"),
    [
        # Processes that can't take console ctrl events are force-terminated
        ("interrupt", True, ["/F", "/T"]),
        ("terminate", False, ["/T"]),
        ("kill", False, ["/F", "/T"]),
    ],
)
def test_windows_process_stop_ends_its_process_tree(
    windows_process_control, fake_subprocess, method, no_console_ctrl, expected_taskkill
):
    subprocess = fake_subprocess()
    process = PoeProcess(cast("Any", subprocess), no_console_ctrl=no_console_ctrl)
    process._is_windows = True

    getattr(process, method)()

    assert subprocess.signals_sent == []
    assert windows_process_control == [
        ["taskkill", *expected_taskkill, "/PID", str(process.pid)]
    ]


def test_windows_interrupt_sends_ctrl_break_to_the_process_group(
    windows_process_control, fake_subprocess
):
    subprocess = fake_subprocess()
    process = PoeProcess(cast("Any", subprocess))
    process._is_windows = True

    process.interrupt()

    assert subprocess.signals_sent == [signal.CTRL_BREAK_EVENT]  # type: ignore[attr-defined]
    assert windows_process_control == []


def test_windows_interrupt_tolerates_failing_to_send_ctrl_break(
    windows_process_control, fake_subprocess
):
    # Escalating to terminate stops the process if the event can't be delivered
    def send_signal(sig: int):
        raise OSError("no console")

    subprocess = fake_subprocess()
    subprocess.send_signal = send_signal
    process = PoeProcess(cast("Any", subprocess))
    process._is_windows = True

    process.interrupt()


async def _start_process(*cmd: str) -> PoeProcess:
    """
    Start a subprocess with its stdout piped, in a new process group as poe does.
    """
    new_group: dict[str, Any] = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if sys.platform == "win32"
        else {"start_new_session": True}
    )
    return PoeProcess(
        await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, **new_group
        )
    )


async def _read_output(process: PoeProcess) -> list[bytes]:
    return b"".join([chunk async for chunk in process.read_output()]).splitlines()


def _hold_output_cmd(pid_file, hold_ms: int, tick_ms: int = 0) -> list[str]:
    hold_output = shutil.which("poe_test_hold_output")
    assert hold_output
    return [hold_output, str(pid_file), str(hold_ms), str(tick_ms)]


@pytest.mark.asyncio
async def test_read_output_reads_until_the_output_closes():
    process = await _start_process(
        sys.executable, "-c", "import sys; sys.stdout.write('x' * 1_000_000)"
    )
    assert await _read_output(process) == [b"x" * 1_000_000]


@pytest.mark.asyncio
async def test_read_output_reads_everything_written_before_exit_for_a_slow_consumer(
    monkeypatch,
):
    monkeypatch.setattr(executor_base, "OUTPUT_DEADLINE_S", 0.2)
    process = await _start_process(
        sys.executable, "-c", "import sys; sys.stdout.write('x' * 300_000)"
    )
    received = []
    async for chunk in process.read_output(16 * 1024):
        received.append(chunk)
        # Takes far longer to consume the output than the deadline allows
        await asyncio.sleep(0.05)
    assert b"".join(received) == b"x" * 300_000


@pytest.mark.asyncio
async def test_wait_returns_when_the_process_exits_while_its_output_is_held_open(
    output_holder_pid_file,
):
    process = await _start_process(*_hold_output_cmd(output_holder_pid_file, 30_000))
    # Far less than the detached process holds the output open for
    assert await asyncio.wait_for(process.wait(), 15) == 0
    # Then finish with the output, as poe does, so the held pipe gets closed
    assert await asyncio.wait_for(_read_output(process), 15) == [b"started"]


@pytest.mark.asyncio
async def test_read_output_stops_once_held_output_goes_quiet(
    monkeypatch, output_holder_pid_file
):
    monkeypatch.setattr(executor_base, "OUTPUT_DEADLINE_S", 60)
    process = await _start_process(*_hold_output_cmd(output_holder_pid_file, 30_000))
    assert await asyncio.wait_for(_read_output(process), 15) == [b"started"]


@pytest.mark.asyncio
async def test_read_output_stops_at_the_deadline_while_held_output_continues(
    monkeypatch, output_holder_pid_file
):
    monkeypatch.setattr(executor_base, "OUTPUT_IDLE_TIMEOUT_S", 60)
    monkeypatch.setattr(executor_base, "OUTPUT_DEADLINE_S", 1)
    process = await _start_process(
        *_hold_output_cmd(output_holder_pid_file, 30_000, tick_ms=100)
    )
    lines = await asyncio.wait_for(_read_output(process), 15)
    assert b"started" in lines
    assert b"tick" in lines
