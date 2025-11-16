from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Coroutine

T = TypeVar("T")


def run_async(func: Coroutine[Any, Any, T]) -> T:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in an event loop, run as a task and wait for result
        return asyncio.run_coroutine_threadsafe(func, loop).result()
    else:
        return asyncio.run(func)


async def async_noop(result=None, *args, **kwargs) -> Any:
    return result


_SENTINEL = object()


async def async_iter_merge(
    *sources: AsyncIterable[T],
    generator: AsyncIterable[AsyncIterable[T]] | None = None,
    buffer_length: int = 10,
) -> AsyncIterator[T]:
    """
    Fan-in merge of multiple async iterables using a shared Queue.
    Async iterables to merge can be provided directly as `sources` or via an async
    generator function that yields async iterables.

    Semantics:
      - Interleaves items as they arrive; per-source order is preserved.
      - Backpressure: producers block on q.put when `maxsize` is reached.
      - If any source raises (except StopAsyncIteration), the exception is
        propagated and remaining sources are cancelled.
      - Completes when all sources are exhausted.
    """
    # Materialize iterators so we can aclose() them on shutdown.
    iters: list[AsyncIterator[T]] = [source.__aiter__() for source in sources]
    queue: asyncio.Queue[tuple[int, object]] = asyncio.Queue(maxsize=buffer_length)

    async def pump(idx: int, it: AsyncIterator[T]) -> None:
        try:
            async for item in it:
                await queue.put((idx, item))
        except Exception as e:
            # Propagate errors to the consumer
            await queue.put((idx, e))
        finally:
            # Always signal completion for this source (best-effort)
            with contextlib.suppress(asyncio.CancelledError):
                await queue.put((idx, _SENTINEL))

    pump_tasks = [
        asyncio.create_task(pump(idx, it), name=f"async_iter_merge:pump:{idx}")
        for idx, it in enumerate(iters)
    ]
    finished: set[int] = set()

    if generator:

        async def meta_pump(meta_src: AsyncIterable[AsyncIterable[T]]) -> None:
            async for src in meta_src:
                iters.append(src.__aiter__())  # type: ignore[call-arg]
                pump_tasks.append(
                    asyncio.create_task(
                        pump(len(iters) - 1, iters[-1]),
                        name=f"async_iter_merge:meta_pump:pump:{len(iters) - 1}",
                    )
                )

        pump_tasks.append(
            asyncio.create_task(
                meta_pump(generator), name="async_iter_merge:meta_pump}"
            )
        )

    try:
        while len(finished) < len(iters):
            idx, payload = await queue.get()

            if payload is _SENTINEL:
                finished.add(idx)
                continue

            if isinstance(payload, Exception):
                # Cancel all pump_tasks and re-raise the source error
                for task in pump_tasks:
                    task.cancel()
                # Best-effort close remaining iterators
                for it in iters:
                    if getattr(it, "aclose", None):
                        with contextlib.suppress(BaseException):
                            await it.aclose()  # type: ignore[attr-defined]
                raise payload
            yield payload  # type: ignore[misc]
    finally:
        for task in pump_tasks:
            task.cancel()
        # Close any still-open iterators (async generators support aclose())
        for it in iters:
            if getattr(it, "aclose", None):
                with contextlib.suppress(BaseException):
                    await it.aclose()  # type: ignore[attr-defined]


class DynamicTaskSet:
    """
    This is a python <3.11 compatible approximation of asyncio.TaskGroup
    TODO: Replace with asyncio.TaskGroup when we drop support for python <3.11
    """

    def __init__(self, *, cancel_on_error: bool = True):
        self._tasks: set[asyncio.Task] = set()
        self._cancel_on_error = cancel_on_error
        self._first_exception: BaseException | None = None
        self._closed = False

    def __len__(self):
        return len(self._tasks)

    def __iter__(self):
        return iter(self._tasks)

    async def __aenter__(self):
        return self

    def create_task(self, coro: Coroutine, name: str) -> asyncio.Task:
        if self._closed:
            raise RuntimeError("Cannot create task in closed DynamicTaskSet")
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)

        def _done(task: asyncio.Task):
            self._tasks.discard(task)
            if (
                self._cancel_on_error
                and not task.cancelled()
                and (exception := task.exception()) is not None
                and self._first_exception is None
            ):
                self._first_exception = exception
                self.close()

        task.add_done_callback(_done)
        return task

    def _cancel_all(self):
        for task in list(self._tasks):
            task.cancel()

    async def wait(self):
        while self._tasks:
            await asyncio.wait(self._tasks, return_when=asyncio.FIRST_COMPLETED)

    def exception(self) -> BaseException | None:
        return self._first_exception

    def close(self):
        self._cancel_all()
        self._closed = True

    async def __aexit__(self, et, ev, tb):
        try:
            await self.wait()
        except asyncio.CancelledError:
            self._cancel_all()
            raise
        finally:
            # Ensure cleanup of remaining tasks
            if self._cancel_on_error:
                self._cancel_all()
            await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._first_exception and et is None:
            raise self._first_exception
