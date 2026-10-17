from __future__ import annotations

import asyncio
import contextlib
import signal
from typing import TYPE_CHECKING
from weakref import WeakSet

if TYPE_CHECKING:
    from .executor.base import PoeProcess
    from .io import PoeIO

ESCALATION_INTERVAL_S = 0.8


def signal_shutdown(process: PoeProcess, urgency: int) -> None:
    """
    Signal a subprocess to shut down with the given urgency, which escalates the same
    way as repeatedly pressing ctrl+c: 1 or 2 interrupts it, 3 asks it to terminate,
    and 4 or more kills it.

    Each urgency level is only signalled once per subprocess, so that a shutdown and
    an aborting task stopping the same subprocess share one escalation.
    """
    if process.returncode is not None or urgency <= process.shutdown_urgency:
        return
    process.shutdown_urgency = urgency
    if urgency < 3:
        process.interrupt()
    elif urgency == 3:
        process.terminate()
    else:
        process.kill()


async def stop_process(
    process: PoeProcess, escalation_interval_s: float = ESCALATION_INTERVAL_S
) -> None:
    """
    Stop a subprocess as if ctrl+c were pressed, escalating the urgency each interval
    until it exits.
    """
    urgency = 1
    while process.returncode is None:
        signal_shutdown(process, urgency)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(process.wait(), escalation_interval_s)
        urgency += 1


class ShutdownManager:
    """Manages graceful and forceful shutdown of tasks and subprocesses"""

    def __init__(self, loop: asyncio.AbstractEventLoop, io: PoeIO):
        self._loop = loop
        self._io = io
        self._shutting_down = asyncio.Event()
        self._urgency = 0
        self.tasks: WeakSet[asyncio.Task] = WeakSet()
        self.processes: WeakSet[PoeProcess] = WeakSet()
        self._backup_sighup = None
        self._backup_sigint = None
        self._backup_sigterm = None
        self._backup_sigbreak = None
        self._shutdown_worker: asyncio.Task | None = None

    def shutdown(self, signum=None, frame=None):
        self._io.print_debug(" ! Termination requested with signal: '%s'", signum or "")
        if signum is signal.SIGTERM:
            self._urgency += max(1, 3 - self._urgency)
        else:
            self._urgency += 1
        self._loop.call_soon_threadsafe(self._initialize_shutdown)

    def _initialize_shutdown(self):
        if self._shutdown_worker:
            self._shutdown_worker.cancel()
        self._shutdown_worker = self._loop.create_task(
            self._shutdown_loop(), name="ShutdownWorker"
        )

    async def _shutdown_loop(
        self, escalation_interval_s: float = ESCALATION_INTERVAL_S
    ):
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
        for proc in tuple(self.processes):
            if proc.returncode is None:
                signal_shutdown(proc, self._urgency)
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

        if self._urgency >= 4:
            # Stop waiting on subprocesses once they have been killed
            self.processes.clear()

    def _propagate_sighup(self, signum=None, frame=None):
        """
        If we receive SIGHUP then this means the parent TTY has closed. Since tasks run
        in process groups we need to explicitly propagate the SIGHUP to them, and then
        trigger shutdown so poe exits cleanly.
        """
        self._io.print_debug(" ! SIGHUP received: propagating to subprocess groups")
        for proc in tuple(self.processes):
            if proc.returncode is None:
                proc.signal_group(signal.SIGHUP)
            else:
                self.processes.discard(proc)
        # Also trigger shutdown so poe exits cleanly
        self.shutdown(signum, frame)

    def install_handler(self):
        if hasattr(signal, "SIGHUP"):
            self._backup_sighup = signal.signal(signal.SIGHUP, self._propagate_sighup)
        self._backup_sigint = signal.signal(signal.SIGINT, self.shutdown)
        if hasattr(signal, "SIGTERM"):
            self._backup_sigterm = signal.signal(signal.SIGTERM, self.shutdown)
        if hasattr(signal, "SIGBREAK"):  # Windows
            self._backup_sigbreak = signal.signal(signal.SIGBREAK, self.shutdown)

    def restore_handler(self):
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, self._backup_sighup or signal.SIG_DFL)
        signal.signal(signal.SIGINT, self._backup_sigint or signal.SIG_DFL)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, self._backup_sigterm or signal.SIG_DFL)
        if hasattr(signal, "SIGBREAK"):  # Windows
            signal.signal(signal.SIGBREAK, self._backup_sigbreak or signal.SIG_DFL)
