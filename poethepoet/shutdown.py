from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import subprocess
import sys
from typing import TYPE_CHECKING
from weakref import WeakSet

if TYPE_CHECKING:
    from asyncio.subprocess import Process

    from .io import PoeIO


class ShutdownManager:
    """Manages graceful and forceful shutdown of tasks and subprocesses"""

    def __init__(self, loop: asyncio.AbstractEventLoop, io: PoeIO):
        self._loop = loop
        self._io = io
        self._shutting_down = asyncio.Event()
        self._urgency = 0
        self.tasks: WeakSet[asyncio.Task] = WeakSet()
        self.processes: WeakSet[Process] = WeakSet()
        self._backup_sigint = None
        self._backup_sigterm = None
        self._is_windows = sys.platform == "win32"
        self._shutdown_worker: asyncio.Task | None = None

    def shutdown(self, signum=None, frame=None):
        self._io.print_debug(" ! Termination requested with signal: '%s'", signum or "")
        if signum is signal.SIGTERM:
            self._urgency += max(1, 3 - self._urgency)
        else:
            self._urgency += 1
        self._loop.call_soon_threadsafe(self._being_shut_down)

    def _being_shut_down(self):
        if self._shutdown_worker:
            self._shutdown_worker.cancel()
        self._shutdown_worker = self._loop.create_task(
            self._shutdown_loop(), name="ShutdownWorker"
        )

    async def _shutdown_loop(self, escalation_interval_s: float = 1.0):
        """
        Call shutdown again every interval_s seconds until everything is dead
        """
        while self.processes or self.tasks:
            self._shutdown()
            await asyncio.sleep(escalation_interval_s)
            self._urgency += 1

    def _shutdown(self):
        self._io.print_debug(
            " ! Shutdown triggered level %s: commencing cleanup", self._urgency
        )
        if self._is_windows:
            for proc in tuple(self.processes):
                if proc.returncode is None:
                    self._io.print_debug(
                        " ! Sending CTRL_BREAK_EVENT to subprocess %s", proc.pid
                    )
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self.processes.discard(proc)
        else:
            for proc in tuple(self.processes):
                if proc.returncode is None:
                    with contextlib.suppress(ProcessLookupError):
                        self._io.print_debug(
                            " ! Sending SIGINT to subprocess group %s", proc.pid
                        )
                        os.killpg(os.getpgid(proc.pid), signal.SIGINT)
                else:
                    self.processes.discard(proc)

        if not self.processes:
            self._io.print_debug(" ! Cleaning up tasks")
            # Clean up async tasks if there are no more subprocesses
            for task in tuple(self.tasks):
                if task.done():
                    self.tasks.discard(task)
                else:
                    self._io.print_debug(" ! Cancelling task: %s", task.get_name())
                    task.cancel()

        if self._urgency >= 3:
            self._io.print_debug(
                " ! Forceful shutdown triggered: terminating subprocesses"
            )
            # Tell subprocesses to terminate
            if self._is_windows:
                for proc in self.processes:
                    if proc.returncode is None:
                        subprocess.run(
                            ["taskkill", "/T", "/PID", str(proc.pid)],
                            capture_output=True,
                        )
                    else:
                        self.processes.discard(proc)
            else:
                while self.processes:
                    proc = self.processes.pop()
                    if proc.returncode is None:
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(os.getpgid(proc.pid), 9)

        if self._urgency >= 4:
            self._io.print_debug(" ! Forceful shutdown triggered: killing subprocesses")
            # Kill subprocesses with extreme prejudice
            if self._is_windows:
                while self.processes:
                    proc = self.processes.pop()
                    if proc.returncode is None:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            capture_output=True,
                        )
            else:
                while self.processes:
                    proc = self.processes.pop()
                    if proc.returncode is None:
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)

    def install_handler(self):
        self._backup_sigint = signal.signal(signal.SIGINT, self.shutdown)
        if hasattr(signal, "SIGTERM"):
            self._backup_sigterm = signal.signal(signal.SIGTERM, self.shutdown)

    def restore_handler(self):
        signal.signal(signal.SIGINT, self._backup_sigint or signal.SIG_DFL)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, self._backup_sigterm or signal.SIG_DFL)
