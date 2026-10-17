import signal

import pytest


@pytest.fixture
def windows_process_control(monkeypatch):
    """
    Stand in for the Windows process control used by PoeProcess, returning the list
    that records each taskkill command run.
    """
    monkeypatch.setattr(
        signal,
        "CTRL_BREAK_EVENT",
        getattr(signal, "CTRL_BREAK_EVENT", 1),
        raising=False,
    )
    taskkill_calls: list[list[str]] = []
    monkeypatch.setattr(
        "subprocess.run", lambda cmd, **_kwargs: taskkill_calls.append(cmd)
    )
    return taskkill_calls
