from typing import Any, cast

import pytest

from poethepoet.executor.base import PoeProcess
from poethepoet.executor.task_run import PoeTaskRun


class FakeProcess:
    """
    A stand-in for an asyncio subprocess that has already exited.
    """

    def __init__(self, returncode: int):
        self.pid = 12345
        self.returncode = returncode


async def _task_run_with_codes(*returncodes: int) -> PoeTaskRun:
    task_run = PoeTaskRun("test")
    for returncode in returncodes:
        await task_run.add_process(PoeProcess(cast("Any", FakeProcess(returncode))))
    await task_run.finalize()
    return task_run


@pytest.mark.asyncio
async def test_return_code_maps_signal_deaths_to_shell_convention():
    # asyncio reports a process killed by signal N as returncode -N, which would
    # otherwise reach the OS as an exit status of 256 - N
    task_run = await _task_run_with_codes(-15)
    assert task_run.return_code == 143


@pytest.mark.asyncio
async def test_return_code_does_not_sum_multiple_failures():
    # Summing 128 + 128 would wrap to an exit status of 0 (mod 256)
    task_run = await _task_run_with_codes(0, 128, 128)
    assert task_run.return_code == 128


@pytest.mark.asyncio
async def test_return_code_reports_first_failure_of_children():
    parent = PoeTaskRun("parent")
    for returncodes in ((0,), (3,), (-2,)):
        await parent.add_child(await _task_run_with_codes(*returncodes))
    await parent.finalize()
    assert parent.return_code == 3


@pytest.mark.asyncio
async def test_return_code_respects_ignored_codes():
    task_run = PoeTaskRun("test")
    task_run.ignore_failure([3])
    await task_run.add_process(PoeProcess(cast("Any", FakeProcess(3))))
    await task_run.add_process(PoeProcess(cast("Any", FakeProcess(4))))
    await task_run.finalize()
    assert task_run.return_code == 4
