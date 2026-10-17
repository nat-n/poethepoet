import os
import signal
import sys
from typing import Any, cast

import pytest

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
