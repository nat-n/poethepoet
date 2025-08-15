import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

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
