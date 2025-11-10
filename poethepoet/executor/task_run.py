from __future__ import annotations

import asyncio
import contextlib
import inspect
from typing import TYPE_CHECKING

from poethepoet.helpers.eventloop import async_iter_merge, async_noop

if TYPE_CHECKING:
    from asyncio.subprocess import Process
    from collections.abc import AsyncIterable, Awaitable, Callable, Coroutine


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
        self._processes: list[Process] = []
        self._update_condition = asyncio.Condition()
        self._ignore_failure = False
        self._force_failure = False
        self._finalized = False
        self._completion_watcher: asyncio.Task | None = None
        self._done_callbacks: list[
            Callable[[PoeTaskRunEvent], None] | Callable[[PoeTaskRunEvent], Awaitable]
        ] = []
        self._new_process_callbacks: list[Callable[[Process], None]] = []

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
        self._force_failure = True

    def ignore_failure(self):
        """
        Ignore any failures in this task, always returning zero return code.
        """
        self._ignore_failure = True
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
        tasks completes or fails.
        """
        queue: asyncio.Queue[PoeTaskRunEvent] = asyncio.Queue()
        unsubscribe = self.subscribe(queue.put_nowait)
        try:
            while not self.done() or not queue.empty():
                yield await queue.get()
        finally:
            unsubscribe()

    def add_new_process_callback(
        self, callback: Callable[[Process], None]
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

    def _notify_new_process(self, process: Process) -> None:
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
        if self.asyncio_task.exception():
            await self.kill()

    async def _watch_completion(self) -> None:
        await self.wait()

        event = (
            PoeTaskRunCompletion(self.name)
            if not self.has_failure
            else PoeTaskRunError(self.name, exception=self.asyncio_task.exception())
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
        if self._ignore_failure:
            return False

        return (
            self.asyncio_task.cancelled()
            or (self.asyncio_task.done() and self.asyncio_task.exception() is not None)
            or any(process.returncode != 0 for process in self._processes)
            or any(child.has_failure for child in self._children)
            or self._force_failure
        )

    @property
    def return_code(self) -> int | None:
        """
        Return the combined return code of all processes and child tasks, or None if any
        are still running.
        If force_failure is set, return at least 1 if everything else is zero.
        If ignore_failure is set, always return 0 regardless of actual return codes.
        """
        if any(process.returncode is None for process in self._processes):
            return None
        if any(child.return_code is None for child in self._children):
            return None
        if self._ignore_failure:
            return 0
        return sum(
            process.returncode or 0 for process in self._processes if process.returncode
        ) + sum(child.return_code or 0 for child in self._children) or int(
            self._force_failure
        )

    async def add_process(self, process: Process, finalize: bool = False) -> PoeTaskRun:
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
        self._finalized = True
        if asyncio.current_task() is not self.asyncio_task:
            self.asyncio_task.cancel()
        for process in self._processes:
            if process.returncode is None:
                process.kill()
        for child in self._children:
            await child.kill()
        await self._notify_update()

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

    def subscribe(
        self, callback: Callable[[PoeTaskRunEvent], None]
    ) -> Callable[[], None]:
        """
        Subscribe to events on this task run. The callback will be called with a
        PoeTaskRunEvent when the task or any of its direct child tasks completes or
        fails.
        """
        cancel_callbacks = [
            self.add_done_callback(callback),
            *(child.add_done_callback(callback) for child in self._children),
        ]

        def unsubscribe():
            for cancel_callback in cancel_callbacks:
                cancel_callback()

        return unsubscribe

    async def processes(self) -> AsyncIterable[tuple[PoeTaskRun, Process]]:
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

    async def _iter_processes(self) -> AsyncIterable[tuple[PoeTaskRun, Process]]:
        cursor = 0
        while cursor < len(self._processes) or not self.finalized():
            if cursor < len(self._processes):
                process = self._processes[cursor]
                yield self, process
                cursor += 1
            else:
                await self._wait_for_update()
