# ruff: noqa: PT012

"""
AI Generated tests, better than nothing for now.
"""

import asyncio

import pytest

from poethepoet.helpers.eventloop import async_iter_merge


def _make_async_gen(items, delay: float = 0.001, on_close: asyncio.Event | None = None):
    async def _gen():
        try:
            for item in items:
                await asyncio.sleep(delay)
                yield item
        finally:
            if on_close:
                on_close.set()

    return _gen


def _make_raising_gen(exc: Exception, delay=0.01):
    async def _gen():
        await asyncio.sleep(delay)
        raise exc
        yield  # pragma: no cover

    return _gen


@pytest.mark.asyncio
async def test_aclose_called_on_normal_completion():
    closed = asyncio.Event()
    async_gen = _make_async_gen([1, 2, 3], on_close=closed)()

    assert [item async for item in async_iter_merge(async_gen)] == [
        1,
        2,
        3,
    ]
    await asyncio.wait_for(closed.wait(), timeout=1.0)


@pytest.mark.asyncio
@pytest.mark.skip
async def test_meta_generator_exception_closes_previously_added_sources():
    # first source is long lived and should be closed when meta raises
    closed = asyncio.Event()

    async def long_gen():
        try:
            for i in range(100):
                await asyncio.sleep(0.02)
                yield ("long", i)
        finally:
            closed.set()

    async def meta():
        # yield a long-lived generator, then raise
        yield long_gen()
        await asyncio.sleep(0.01)
        raise RuntimeError("meta boom")

    with pytest.raises(RuntimeError):
        async for _ in async_iter_merge(generator=meta(), buffer_length=2):
            await asyncio.sleep(0)

    await asyncio.wait_for(closed.wait(), timeout=1.0)


@pytest.mark.asyncio
async def test_consumer_break_triggers_producer_close():
    closed = asyncio.Event()
    async_gen = _make_async_gen(range(100), on_close=closed)()

    # consume only one item then break out of loop
    async for item in async_iter_merge(async_gen, buffer_length=3):
        assert item == 0
        break

    # ensure producer was aclosed/closed after consumer stops
    await asyncio.wait_for(closed.wait(), timeout=1.0)


@pytest.mark.asyncio
async def test_many_sources_preserve_per_source_order():
    # create 5 sources, each yields 3 incremental numbers
    sources = [
        _make_async_gen(list(range(idx * 100, idx * 100 + 3)))() for idx in range(5)
    ]
    collected = [item async for item in async_iter_merge(*sources, buffer_length=10)]

    # check each source's subsequence appears in order
    for idx in range(5):
        expected = list(range(idx * 100, idx * 100 + 3))
        found = [x for x in collected if x in expected]
        assert found == expected


@pytest.mark.asyncio
@pytest.mark.skip
async def test_exception_from_dynamic_source_propagates_and_closes_others():
    closed = asyncio.Event()

    async def good():
        try:
            yield 1
            await asyncio.sleep(0.05)
            yield 2
        finally:
            closed.set()

    async def meta():
        yield good()
        await asyncio.sleep(0.01)
        yield _make_raising_gen(RuntimeError("boom"), delay=0.01)()

    with pytest.raises(RuntimeError):
        async for _ in async_iter_merge(generator=meta(), buffer_length=3):
            await asyncio.sleep(0)

    await asyncio.wait_for(closed.wait(), timeout=1.0)
