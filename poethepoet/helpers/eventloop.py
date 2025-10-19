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

    pump_tasks = [asyncio.create_task(pump(idx, it)) for idx, it in enumerate(iters)]
    finished: set[int] = set()

    if generator:

        async def meta_pump(meta_src: AsyncIterable[AsyncIterable[T]]) -> None:
            async for src in meta_src:
                iters.append(src.__aiter__())  # type: ignore[call-arg]
                pump_tasks.append(asyncio.create_task(pump(len(iters) - 1, iters[-1])))

        pump_tasks.append(asyncio.create_task(meta_pump(generator)))

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
