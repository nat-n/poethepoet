import asyncio

import pytest

from poethepoet.executor.task_run import PoeTaskRun


@pytest.fixture
def task_run_with_codes(fake_poe_process):
    async def task_run_with_codes(*returncodes: int) -> PoeTaskRun:
        task_run = PoeTaskRun("test")
        for returncode in returncodes:
            await task_run.add_process(fake_poe_process(returncode))
        await task_run.finalize()
        return task_run

    return task_run_with_codes


@pytest.mark.asyncio
async def test_return_code_maps_signal_deaths_to_shell_convention(task_run_with_codes):
    # asyncio reports a process killed by signal N as returncode -N, which would
    # otherwise reach the OS as an exit status of 256 - N
    task_run = await task_run_with_codes(-15)
    assert task_run.return_code == 143


@pytest.mark.asyncio
async def test_return_code_does_not_sum_multiple_failures(task_run_with_codes):
    # Summing 128 + 128 would wrap to an exit status of 0 (mod 256)
    task_run = await task_run_with_codes(0, 128, 128)
    assert task_run.return_code == 128


@pytest.mark.asyncio
async def test_return_code_reports_first_failure_of_children(task_run_with_codes):
    parent = PoeTaskRun("parent")
    for returncodes in ((0,), (3,), (-2,)):
        await parent.add_child(await task_run_with_codes(*returncodes))
    await parent.finalize()
    assert parent.return_code == 3


@pytest.mark.asyncio
async def test_return_code_respects_ignored_codes(fake_poe_process):
    task_run = PoeTaskRun("test")
    task_run.ignore_failure([3])
    await task_run.add_process(fake_poe_process(3))
    await task_run.add_process(fake_poe_process(4))
    await task_run.finalize()
    assert task_run.return_code == 4


@pytest.mark.asyncio
async def test_return_code_does_not_count_processes_killed_with_the_task_run(
    task_run_with_codes, fake_poe_process
):
    # A sibling that is killed because another subtask failed is a consequence of
    # the failure, so it must not be reported in place of the code of the cause
    parent = PoeTaskRun("parent")
    killed_sibling = PoeTaskRun("killed_sibling")
    await killed_sibling.add_process(fake_poe_process())
    await killed_sibling.finalize()
    await parent.add_child(killed_sibling)
    await parent.add_child(await task_run_with_codes(3))
    await parent.finalize()

    await parent.kill()
    assert killed_sibling.has_failure
    assert parent.return_code == 3


@pytest.mark.asyncio
async def test_kill_interrupts_processes_once_when_called_repeatedly(
    fake_poe_process,
):
    # A task run is commonly killed both by its aborting parent and by its own
    # cancellation, which must not send a process two interrupts, because a second
    # ctrl+c often means skipping a graceful shutdown
    parent = PoeTaskRun("parent")
    child = PoeTaskRun("child")
    await child.add_process(process := fake_poe_process())
    await child.finalize()
    await parent.add_child(child)
    await parent.finalize()

    await asyncio.gather(parent.kill(), child.kill(), child.kill())

    assert process.stop_requests == ["interrupt"]
    assert process.returncode == -2


@pytest.mark.asyncio
async def test_wait_includes_stopping_processes_of_a_killed_task_run(
    fake_poe_process,
):
    task_run = PoeTaskRun("test")
    await task_run.add_process(fake_poe_process(stops_on="terminate"))
    await task_run.finalize()

    kill_task = asyncio.create_task(task_run.kill())
    await task_run.wait()

    assert kill_task.done()
    assert task_run.return_code == 0  # The killed process is not counted


@pytest.mark.asyncio
async def test_return_code_reports_the_child_that_failed_first_in_time(
    fake_poe_process,
):
    parent = PoeTaskRun("parent")
    processes = []
    for name in ("declared_first", "declared_second"):
        processes.append(process := fake_poe_process())
        child = PoeTaskRun(name)
        await child.add_process(process, finalize=True)
        await parent.add_child(child)
    await parent.finalize()

    processes[1].exit(3)
    # Let the failure of the second child be observed before the first one fails
    for _ in range(10):
        await asyncio.sleep(0)
    processes[0].exit(2)
    await parent.wait()

    assert parent.return_code == 3
