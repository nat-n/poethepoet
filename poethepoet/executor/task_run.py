from __future__ import annotations

import asyncio
import contextlib
import inspect
from typing import TYPE_CHECKING

from ..helpers.eventloop import async_iter_merge, async_noop
from ..shutdown import stop_process

if TYPE_CHECKING:
    from collections.abc import (
        AsyncIterable,
        Awaitable,
        Callable,
        Collection,
        Coroutine,
    )

    from .base import PoeProcess


def _as_exit_status(return_code: int) -> int:
    """
    Map a subprocess return code to a shell style exit status. asyncio reports a
    process killed by signal N as -N, which the shell convention reports as 128 + N.
    """
    return 128 - return_code if return_code < 0 else return_code


class PoeTaskRunEvent:
    """
    An event that is emitted when a PoeTaskRun completes or fails.
    """

    name: str | None = None

    def __init__(self, name: str, exception: BaseException | None = None):
        self.name = name

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name}>"


class PoeTaskRunError(PoeTaskRunEvent):
    exception: BaseException | None = None

    def __init__(self, name: str, exception: BaseException | None = None):
        super().__init__(name)
        self.exception = exception

    def __str__(self) -> str:
        return f"<PoeTaskRunError name={self.name} exception={self.exception}>"


class PoeTaskRunCompletion(PoeTaskRunEvent):
    pass


class PoeTaskRun:
    """
    Represents the execution of a Poe task, including its subprocesses and any child
    tasks it may spawn.
    """

    _parent: PoeTaskRun | None = None
    _ignore_failure: bool = False
    _ignore_failure_codes: Collection[int] = ()

    def __init__(
        self,
        name: str,
        task_callable: Callable[[PoeTaskRun], Coroutine] = async_noop,
    ):
        self.name = name
        self.asyncio_task = asyncio.create_task(
            task_callable(self), name=f"PoeTaskRun:{self.name}"
        )
        self.asyncio_task.add_done_callback(
            lambda event: asyncio.create_task(
                self._handle_asyncio_task_done(),
                name=f"PoeTaskRun._handle_asyncio_task_done:{self.name}",
            )
        )
        self._children: list[PoeTaskRun] = []
        self._failed_children: list[PoeTaskRun] = []
        self._processes: list[PoeProcess] = []
        self._killed_processes: set[PoeProcess] = set()
        self._update_condition = asyncio.Condition()
        self._force_failure = False
        self._finalized = False
        self._completion_watcher: asyncio.Task | None = None
        self._stopping: asyncio.Task | None = None
        self._done_callbacks: list[
            Callable[[PoeTaskRunEvent], None] | Callable[[PoeTaskRunEvent], Awaitable]
        ] = []
        self._new_process_callbacks: list[Callable[[PoeProcess], None]] = []

    @property
    def parent(self) -> PoeTaskRun | None:
        return self._parent

    def get_child_index(self, child: PoeTaskRun) -> int:
        """
        Assuming child is a descendant of self, return the index of the immediate child
        of self that is equal to or an ancestor of child. If child is not a descendant
        of self, return -1.
        """
        while child.parent is not None and child.parent != self:
            # Traverse up from child to self to get the immediate child
            child = child.parent
        if not child.parent:
            return -1
        return self._children.index(child)

    def force_failure(self):
        """
        Force the task to fail, even if it would otherwise succeed.
        """
        self._ignore_failure = False
        self._ignore_failure_codes = set()
        self._force_failure = True

    def ignore_failure(
        self,
        ignore_failure: bool | list[int] | str = True,
    ):
        """
        Ignore any failures in this task, always returning zero return code.
        """
        self._ignore_failure = ignore_failure is True or isinstance(ignore_failure, str)
        self._ignore_failure_codes = (
            set(ignore_failure) if isinstance(ignore_failure, list) else set()
        )
        self._force_failure = False

    def finalized(self) -> bool:
        """
        Check if the task and all subtasks have been finalized, meaning no more
        processes or child tasks can be added.
        """
        return self._finalized and all(child.finalized() for child in self._children)

    def done(self) -> bool:
        """
        Check if the task is done, meaning all processes and child tasks have completed.
        """
        return (
            self._finalized
            and all(process.returncode is not None for process in self._processes)
            and all(child.done() for child in self._children)
        )

    async def events(self) -> AsyncIterable[PoeTaskRunEvent]:
        """
        An async generator that yields events when the task or any of its direct child
        tasks completes or fails, until every child present when iteration starts has
        reported its outcome.

        This waits for the events themselves rather than for the children to be done,
        because a child is done slightly before its event is emitted.
        """
        queue: asyncio.Queue[PoeTaskRunEvent] = asyncio.Queue()
        unreported_children = set(self._children)

        def on_child_event(child: PoeTaskRun) -> Callable[[PoeTaskRunEvent], None]:
            def callback(event: PoeTaskRunEvent):
                unreported_children.discard(child)
                queue.put_nowait(event)

            return callback

        cancel_callbacks = [
            self.add_done_callback(queue.put_nowait),
            *(
                child.add_done_callback(on_child_event(child))
                for child in self._children
            ),
        ]
        try:
            while unreported_children or not queue.empty():
                yield await queue.get()
        finally:
            for cancel_callback in cancel_callbacks:
                cancel_callback()

    def add_new_process_callback(
        self, callback: Callable[[PoeProcess], None]
    ) -> Callable[[], None]:
        """
        Add a callback to be called when a new process is added to this task run.
        The callback will be called with the task name and the process.
        """
        self._new_process_callbacks.append(callback)

        def cancel_callback():
            if callback in self._new_process_callbacks:
                self._new_process_callbacks.remove(callback)

        return cancel_callback

    def _notify_new_process(self, process: PoeProcess) -> None:
        for callback in self._new_process_callbacks:
            callback(process)

    def add_done_callback(
        self,
        callback: (
            Callable[[PoeTaskRunEvent], None] | Callable[[PoeTaskRunEvent], Awaitable]
        ),
    ) -> Callable[[], None]:
        """
        Add a callback to be called when the task completes or fails.
        """
        self._done_callbacks.append(callback)
        if not self._completion_watcher:
            self._completion_watcher = asyncio.create_task(
                self._watch_completion(),
                name=f"PoeTaskRun._watch_completion:{self.name}",
            )

        def cancel_callback():
            if callback in self._done_callbacks:
                self._done_callbacks.remove(callback)

        return cancel_callback

    async def _handle_asyncio_task_done(self):
        await self.finalize()
        if self.asyncio_task.cancelled() or self.asyncio_task.exception():
            await self.kill()

    async def _watch_completion(self) -> None:
        await self.wait()

        event = (
            PoeTaskRunCompletion(self.name)
            if not self.has_failure
            else PoeTaskRunError(
                self.name,
                exception=(
                    None
                    if self.asyncio_task.cancelled()
                    else self.asyncio_task.exception()
                ),
            )
        )

        await self._notify_and_clear_done_callbacks(event)
        self._clear_completion_watcher()

    async def _notify_and_clear_done_callbacks(self, event: PoeTaskRunEvent) -> None:
        while self._done_callbacks:
            callback = self._done_callbacks.pop()
            if inspect.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)

    def _clear_completion_watcher(self) -> None:
        if self._completion_watcher:
            self._completion_watcher.cancel()
            self._completion_watcher = None

    @property
    def has_failure(self) -> bool:
        """
        Check if the task has failed. A task is considered failed if any of its
        processes or child tasks have failed, unless ignore_failure is set.
        """
        if self._ignore_failure and not self._ignore_failure_codes:
            return False

        ignore_failure_codes = (0, *self._ignore_failure_codes)

        return (
            self.asyncio_task.cancelled()
            or (self.asyncio_task.done() and self.asyncio_task.exception() is not None)
            or any(
                process.returncode not in ignore_failure_codes
                for process in self._processes
            )
            or any(child.has_failure for child in self._children)
            or self._force_failure
        )

    @property
    def return_code(self) -> int | None:
        """
        Return the combined return code of all processes and child tasks, or None if any
        are still running.
        The combined return code is that of the first process or child task with a
        non-ignored failure. Child tasks are considered in the order that they were
        seen to fail, which matters when they run in parallel, and otherwise in the
        order they were added. A process killed by signal N is reported as 128 + N,
        following the shell convention. Processes that were
        killed along with this task run are not counted, because they are a
        consequence of the failure rather than its cause.
        If force_failure is set, return at least 1 if everything else is zero.
        If ignore_failure is set, always return 0 regardless of actual return codes.
        """
        if any(process.returncode is None for process in self._processes):
            return None
        child_return_codes = [
            child.return_code
            for child in (
                *self._failed_children,
                *(
                    child
                    for child in self._children
                    if child not in self._failed_children
                ),
            )
        ]
        if any(return_code is None for return_code in child_return_codes):
            return None
        if self._ignore_failure and not self._ignore_failure_codes:
            return 0

        ignore_failure_codes = (0, *self._ignore_failure_codes)
        return next(
            (
                _as_exit_status(return_code)
                for return_code in (
                    *(
                        process.returncode
                        for process in self._processes
                        if process not in self._killed_processes
                    ),
                    *child_return_codes,
                )
                if return_code is not None and return_code not in ignore_failure_codes
            ),
            int(self._force_failure),
        )

    async def add_process(
        self, process: PoeProcess, finalize: bool = False
    ) -> PoeTaskRun:
        if self._finalized:
            raise RuntimeError("Cannot add process to completed PoeTaskRun")
        self._processes.append(process)
        if finalize:
            self._finalized = True
        self._notify_new_process(process)
        await self._notify_update()
        return self

    async def add_child(self, child: PoeTaskRun) -> PoeTaskRun:
        if self._finalized:
            raise RuntimeError("Cannot add child to completed PoeTaskRun")
        self._children.append(child)
        child._parent = self
        await self._notify_update()

        async def notify(event: PoeTaskRunEvent):
            if isinstance(event, PoeTaskRunError):
                # Keep track of the order in which child tasks fail
                self._failed_children.append(child)
            await self._notify_update()

        child.add_done_callback(notify)
        return self

    async def finalize(self):
        """
        Finalize the task run, indicating that no more processes or child tasks will be
        added.
        """
        self._finalized = True
        await self._notify_update()
        return self

    async def kill(self):
        """
        Stop this task run along with its child task runs. Running processes are
        stopped the same way as on ctrl+c, escalating until they exit.
        """
        # Shielded so that a cancelled caller doesn't abandon stopping for the others
        await asyncio.shield(self._start_stopping())

    def _start_stopping(self) -> asyncio.Task:
        """
        Immediately stop this task run and its descendants from doing anything more,
        then stop their running processes in the background.
        """
        if self._stopping:
            return self._stopping

        self._finalized = True
        if asyncio.current_task() is not self.asyncio_task:
            self.asyncio_task.cancel()
        stopping_children = [child._start_stopping() for child in self._children]
        running_processes = [
            process for process in self._processes if process.returncode is None
        ]
        self._killed_processes.update(running_processes)
        self._stopping = asyncio.create_task(
            self._stop(running_processes, stopping_children),
            name=f"PoeTaskRun._stop:{self.name}",
        )
        return self._stopping

    async def _stop(
        self,
        processes: Collection[PoeProcess],
        stopping_children: Collection[Awaitable],
    ):
        await self._notify_update()
        await asyncio.gather(
            *(stop_process(process) for process in processes), *stopping_children
        )

    async def wait(self, suppress_errors: bool = True) -> None:
        while not self._finalized:
            await self._wait_for_update()

        if suppress_errors:
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await self.asyncio_task
        else:
            await self.asyncio_task

        for process in self._processes:
            await process.wait()
        for child in self._children:
            # Always suppress errors from child tasks, because it is the parent's
            # responsibility to handle them according to its own ignore_failure setting.
            await child.wait(suppress_errors=True)

        if self._stopping:
            # Let a kill in progress finish, without being affected by its outcome
            await asyncio.wait([self._stopping])

    async def processes(self) -> AsyncIterable[tuple[PoeTaskRun, PoeProcess]]:
        """
        Yield (task name, process) tuples for all processes involved in this task run or
        any child task runs.
        """
        async for task_run, process in async_iter_merge(
            self._iter_processes(),
            generator=(child.processes() async for child in self._iter_children()),
        ):
            yield task_run, process

    async def _wait_for_update(self):
        async with self._update_condition:
            await self._update_condition.wait()

    async def _notify_update(self):
        async with self._update_condition:
            self._update_condition.notify_all()

    async def _iter_children(self) -> AsyncIterable[PoeTaskRun]:
        cursor = 0
        while cursor < len(self._children) or not self.finalized():
            if cursor < len(self._children):
                child = self._children[cursor]
                yield child
                cursor += 1
            else:
                await self._wait_for_update()

    async def _iter_processes(self) -> AsyncIterable[tuple[PoeTaskRun, PoeProcess]]:
        cursor = 0
        while cursor < len(self._processes) or not self.finalized():
            if cursor < len(self._processes):
                process = self._processes[cursor]
                yield self, process
                cursor += 1
            else:
                await self._wait_for_update()
