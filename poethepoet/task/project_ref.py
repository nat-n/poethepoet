"""
Support for running a task from another poe project within the current run, as for a
ref task with the project option.

This duplicates the parts of PoeThePoet needed to load a project and run one of its
tasks, with the differences that a ref task requires: the config path comes from the
project option, task specs are validated lazily, errors are raised to the calling task,
and the run context is a child of the caller's.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..exceptions import ExecutionError, PoeException
from ..io import PoeIO
from .base import TaskContext

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..config import PoeConfig
    from ..context import RunContext
    from ..env.task_env import TaskEnv
    from ..executor.task_run import PoeTaskRun
    from .base import PoeTask, TaskSpecFactory


@dataclass
class LoadedProject:
    """
    A project loaded for running its tasks from another project within the same run.
    """

    config: PoeConfig
    specs: TaskSpecFactory


def resolve_project_path(
    project_template: str, env: TaskEnv, config: PoeConfig
) -> Path:
    """
    Resolve the value of a project option to a path, the same way as the cwd option:
    after templating, a relative path is relative to the project root.
    """
    from ..helpers.parse import parse_template

    project_path = Path(env.fill_template(parse_template(project_template)))
    if not project_path.is_absolute():
        project_path = config.project_dir.joinpath(project_path).resolve()
    return project_path


async def load_project(config_file: Path, io: PoeIO) -> LoadedProject:
    """
    Load the project with the given config file. Its task specs are validated when they
    are first looked up, so that invalid tasks the caller doesn't reach don't block it.
    """
    from ..config import PoeConfig
    from .base import TaskSpecFactory

    config = PoeConfig(cwd=config_file.parent, io=io)
    await config.load(target_path=config_file)
    return LoadedProject(
        config=config, specs=TaskSpecFactory(config, validate_on_get=True)
    )


def build_target_context(
    project: LoadedProject, task_spec: PoeTask.TaskSpec, parent_ctx: TaskContext
) -> TaskContext:
    """
    Build the TaskContext for a task from the loaded project, run by a task with the
    given parent_ctx. The project's verbosity is the baseline for the task only.
    """
    return TaskContext(
        config=project.config,
        cwd=str(task_spec.source.cwd),
        specs=project.specs,
        io=PoeIO(
            parent=parent_ctx.io,
            baseline_verbosity=task_spec.options.get(
                "verbosity", project.config.verbosity
            ),
        ),
        ui=parent_ctx.ui,
    )


async def run_target(
    task: PoeTask,
    context: RunContext,
    task_state: PoeTaskRun,
    *,
    ignore_fail: bool,
    start_error: Callable[[Exception], Exception],
) -> None:
    """
    Run the target task, and its task graph if it has deps, in the given context,
    adding its runs to task_state as children. Errors raised while starting the target
    are passed through start_error and the result raised instead.
    """
    if task.has_deps():
        try:
            await _run_target_graph(task, context, task_state, start_error)
        except ExecutionError as error:
            if ignore_fail:
                task._warn_subtask_failure(context, error.msg)
            else:
                raise
        await task_state.finalize()
        return

    try:
        target_run = await task.run(context=context)
    except (PoeException, ExecutionError) as error:
        raise start_error(error)
    await task_state.add_child(target_run)
    await task_state.finalize()
    try:
        await target_run.wait(suppress_errors=False)
    except ExecutionError as error:
        if ignore_fail:
            task._warn_subtask_failure(context, error.msg)
        else:
            raise


async def _run_target_graph(
    task: PoeTask,
    context: RunContext,
    task_state: PoeTaskRun,
    start_error: Callable[[Exception], Exception],
) -> None:
    """
    Run the stages of the target's task graph in order, with the target last.
    """
    from .graph import TaskExecutionGraph

    try:
        graph = TaskExecutionGraph(task, context)
    except (PoeException, ExecutionError) as error:
        raise start_error(error)

    for stage in graph.get_execution_plan():
        for stage_task in stage:
            if stage_task == task:
                # The final sink task gets special treatment
                try:
                    sink_task_run = await task.run(context=context)
                except (PoeException, ExecutionError) as error:
                    raise start_error(error)
                await task_state.add_child(sink_task_run)
                # Errors from child task runs are otherwise suppressed, so they must
                # be raised here to fail this task
                await sink_task_run.wait(suppress_errors=False)
                return

            dep_task = await stage_task.run(context=context)
            await task_state.add_child(dep_task)
            await dep_task.wait()
            if dep_task.has_failure:
                raise ExecutionError(
                    f"Task graph aborted after failed task {stage_task.name!r}"
                )
    # This should not be possible to reach
    raise ExecutionError("Task graph did not contain the expected sink task")
