from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

from .exceptions import ExecutionError, PoeException
from .helpers.eventloop import run_async

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence

    from .config import PoeConfig
    from .context import RunContext
    from .executor.task_run import PoeTaskRun
    from .io import PoeIO
    from .task.base import PoeTask, TaskSpecFactory
    from .ui import PoeUi


# The shell convention for the exit status of a process killed by SIGPIPE
SIGPIPE_EXIT_STATUS = 128 + 13


class PoeThePoet:
    """
    :param cwd:
        The directory that poe should take as the current working directory,
        this determines where to look for a pyproject.toml file, defaults to
        ``Path().resolve()``
    :type cwd: Path, optional

    :param config:
        Either a dictionary with the same schema as a pyproject.toml file, or a
        `PoeConfig <https://github.com/nat-n/poethepoet/blob/main/poethepoet/config/config.py>`_
        object to use as an alternative to loading config from a file.
    :type config: dict | PoeConfig, optional

    :param output:
        A stream for the application to write its own output to, defaults to sys.stdout
    :type output: IO, optional

    :param poetry_env_path:
        The path to the poetry virtualenv. If provided then it is used by the
        `PoetryExecutor <https://github.com/nat-n/poethepoet/blob/main/poethepoet/executor/poetry.py>`_,
        instead of having to execute poetry in a subprocess to determine this.
    :type poetry_env_path: str, optional

    :param config_name:
        The name of the file to load tasks and configuration from. If not set then poe
        will search for config by the following file names: pyproject.toml
        poe_tasks.toml poe_tasks.yaml poe_tasks.yml poe_tasks.json
    :type config_name: str, optional

    :param program_name:
        The name of the program that is being run. This is used primarily when
        outputting help messages, defaults to "poe"
    :type program_name: str, optional

    :param env:
        Optionally provide an alternative base environment for tasks to run with.
        If no mapping is provided then ``os.environ`` is used.
    :type env: dict, optional

    :param suppress_args:
        A sequence of identifiers for global arguments that should not be displayed in
        the help message.
    :type suppress_args: Sequence[str], optional
    """

    cwd: Path
    ui: PoeUi
    config: PoeConfig

    _task_specs: TaskSpecFactory | None = None

    def __init__(
        self,
        cwd: Path | str | None = None,
        config: Mapping[str, Any] | PoeConfig | None = None,
        output: PoeIO | IO = sys.stdout,
        poetry_env_path: str | None = None,
        config_name: str | None = None,
        program_name: str = "poe",
        env: Mapping[str, str] | None = None,
        suppress_args: Sequence[str] = ("legacy_project_root",),
    ):
        from .config import PoeConfig
        from .io import PoeIO
        from .ui import PoeUi

        self.cwd = Path(cwd) if cwd else Path().resolve()  # noqa: FURB177

        if self.cwd and self.cwd.is_file():
            config_name = self.cwd.name
            self.cwd = self.cwd.parent

        self.io = (
            PoeIO(
                parent=output,
                make_default=True,
            )
            if isinstance(output, PoeIO)
            else PoeIO(
                output=output,
                error=output,
                make_default=True,
            )
        )

        if isinstance(config, PoeConfig):
            self.config = config
            self.config._io = self.io
        else:
            self.config = PoeConfig(
                cwd=self.cwd, table=config, config_name=config_name, io=self.io
            )
        self.io.configure(baseline=self.config.verbosity)

        self.ui = PoeUi(
            io=self.io,
            program_name=program_name,
            suppress_args=suppress_args,
        )
        self._poetry_env_path = poetry_env_path
        self._env = env if env is not None else os.environ

    def __call__(self, cli_args: Sequence[str], internal: bool = False) -> int:
        """
        :param cli_args:
            A sequence of command line arguments to pass to poe (i.e. sys.argv[1:])
        :param internal:
            Indicates that this is an internal call to run poe, e.g. from a
            plugin hook.
        """

        self.ui.parse_args(cli_args)

        if self.ui["version"]:
            self.ui.print_version()
            return 0

        try:
            return run_async(self._call(internal))
        except asyncio.CancelledError:
            return 1
        except OSError as error:
            if not _is_broken_pipe(error):
                raise
            # Whatever was reading poe's output has stopped, e.g. head, so exit quietly
            # as if killed by SIGPIPE, as a task's own process would be
            _discard_stdout()
            return SIGPIPE_EXIT_STATUS

    async def _call(self, internal: bool = False) -> int:
        should_display_help = self.ui["help"] != Ellipsis

        try:
            await self.config.load(target_path=self.ui["project_root"])
            self.io.configure(baseline=self.config.verbosity)
            for task_spec in self.task_specs.load_all():
                task_spec.validate(self.config, self.task_specs)
        except PoeException as error:
            if should_display_help:
                self.print_help(config_is_valid=False)
                return 0
            self.print_help(error=error)
            return 1

        if should_display_help:
            if (
                isinstance(help_task := self.ui["help"], str)
                and help_task not in self.config.get_tasks()
            ):
                self.print_help(error=PoeException(f"Unrecognized task {help_task!r}"))
                return 1
            self.print_help()
            return 0

        task = self.resolve_task(internal)
        if not task:
            return 1

        if task.has_deps():
            return await self._run_task_graph(task)
        return await self._run_task(task)

    def modify_verbosity(self, offset: int):
        """
        Set the offset by which the verbosity level will be modified in all contexts.
        This is an alternative to using the `-v` and `-q` flags on the CLI.
        """
        self.io.configure(offset=offset)

    @property
    def task_specs(self):
        if not self._task_specs:
            from .task.base import TaskSpecFactory

            self._task_specs = TaskSpecFactory(self.config)
        return self._task_specs

    def resolve_task(self, allow_hidden: bool = False) -> PoeTask | None:
        from .io import PoeIO
        from .task.base import TaskContext

        task = tuple(self.ui["task"])
        if not task:
            try:
                self.print_help(info="No task specified.")
            except PoeException as error:
                self.print_help(error=error)
            return None

        task_name = task[0]
        if task_name not in self.config.get_tasks():
            self.print_help(error=PoeException(f"Unrecognized task {task_name!r}"))
            return None

        if task_name.startswith("_") and not allow_hidden:
            self.print_help(
                error=PoeException(
                    "Tasks prefixed with `_` cannot be executed directly"
                ),
            )
            return None

        task_spec = self.task_specs.get(task_name)
        task_context = TaskContext(
            config=self.config,
            cwd=str(task_spec.source.cwd),
            specs=self.task_specs,
            ui=self.ui,
            io=PoeIO(
                parent=self.io,
                baseline_verbosity=task_spec.options.get(
                    "verbosity", self.io._baseline_verbosity
                ),
            ),
        )
        return task_spec.create_task(invocation=task, ctx=task_context)

    async def _run_task(
        self,
        task: PoeTask,
        context: RunContext | None = None,
        abort_message: str | None = None,
    ) -> int:
        """
        Run the task and return the exit code for it. If an abort_message is given,
        e.g. for a stage of a task graph, a failure is reported with that message, and
        otherwise the exit code is zero, whatever the task's return code.
        """
        async with self.run_context(existing=context) as context:
            task_run: PoeTaskRun | None = None
            try:
                task_run = await task.run(context=context)
                await task_run.wait(suppress_errors=False)
                if abort_message is not None:
                    if task_run.has_failure:
                        raise ExecutionError(abort_message)
                    return context.interrupted_exit_status or 0
                # A task run can fail without a non-zero return code, e.g. if an
                # error raised by a child task run was not propagated
                return (
                    context.interrupted_exit_status
                    or task_run.return_code
                    or int(task_run.has_failure)
                )
            except asyncio.CancelledError:
                if (exit_status := context.interrupted_exit_status) is None:
                    raise
                return exit_status
            except ExecutionError as error:
                if (exit_status := context.interrupted_exit_status) is not None:
                    # The failure is a consequence of the shutdown
                    return exit_status
                self.ui.print_error(error=error)
                return await self._get_failure_exit_code(task_run)
            except PoeException as error:
                self.print_help(error=error)
                return 1

    async def _run_task_graph(self, task: PoeTask) -> int:
        from .task.graph import TaskExecutionGraph

        async with self.run_context(multistage=True) as context:
            try:
                graph = TaskExecutionGraph(task, context)
            except PoeException as error:
                self.print_help(error=error)
                return 1
            except ExecutionError as error:
                self.ui.print_error(error=error)
                return 1

            plan = graph.get_execution_plan()

            for stage in plan:
                for stage_task in stage:
                    if stage_task == task:
                        # The final sink task gets special treatment
                        return await self._run_task(stage_task, context)

                    if exit_code := await self._run_task(
                        stage_task,
                        context,
                        abort_message=(
                            f"Task graph aborted after failed task {stage_task.name!r}"
                        ),
                    ):
                        return exit_code
        return 0

    @staticmethod
    async def _get_failure_exit_code(task_run: PoeTaskRun | None) -> int:
        """
        The exit code to report for a task run that failed with an ExecutionError:
        that of the first process or subtask that failed, or 1 if there is none, e.g.
        because the task failed before it could start a process.
        """
        if task_run is None:
            return 1
        # Wait for any processes that are being killed as a result of the failure,
        # because the return code is not known until they have all exited
        await task_run.wait()
        return task_run.return_code or 1

    @asynccontextmanager
    async def run_context(
        self,
        multistage: bool = False,
        existing: RunContext | None = None,
    ) -> AsyncIterator[RunContext]:
        from .context import RunContext

        if existing is not None:
            yield existing
            return

        async with RunContext.scope(
            config=self.config,
            ui=self.ui,
            env=self._env,
            dry=self.ui["dry_run"],
            poe_active=self._env.get("POE_ACTIVE"),
            multistage=multistage,
            cwd=self.cwd,
        ) as context:
            if self._poetry_env_path:
                # This allows the PoetryExecutor to use the venv from poetry directly
                # this is used by the poetry plugin
                context.exec_cache["poetry_virtualenv"] = self._poetry_env_path
            yield context

    def print_help(
        self,
        info: str | None = None,
        error: str | PoeException | None = None,
        *,
        config_is_valid: bool = True,
    ):
        from .task.args import PoeTaskArgs

        if isinstance(error, str):
            error = PoeException(error)

        try:
            all_tasks = self.config.get_tasks()
        except PoeException:
            if error is None and config_is_valid:
                raise
            # The config is already known to be invalid, so collect tasks leniently
            # in order to still display them
            all_tasks = self.config.get_tasks(strict=False)

        tasks_help: dict[
            str, tuple[str, Sequence[tuple[tuple[str, ...], str, str]], str | None]
        ] = {
            task_name: (
                task.help_text,
                PoeTaskArgs.get_help_content(
                    task.get("args"), task_name, suppress_errors=bool(error)
                ),
                task.group.name if task.group else None,
            )
            for task_name, task in all_tasks.items()
        }

        groups_headings = {
            task.group.name: task.group.heading
            for task in all_tasks.values()
            if task.group
        }

        self.ui.print_help(
            tasks=tasks_help, groups=groups_headings, info=info, error=error
        )


def _is_broken_pipe(error: OSError) -> bool:
    """
    Check whether an error is from writing to a pipe that is no longer read. Windows
    can report this as EINVAL rather than EPIPE, which errors about a file name, e.g.
    an invalid one, also use.
    """
    import errno

    return isinstance(error, BrokenPipeError) or (
        sys.platform == "win32"
        and error.errno == errno.EINVAL
        and error.filename is None
    )


def _discard_stdout() -> None:
    """
    Point stdout at the null device, so that writing to it, including the flush on
    exit, doesn't fail again once its pipe is broken.
    """
    with suppress(OSError, ValueError):
        devnull = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull, sys.stdout.fileno())
        finally:
            os.close(devnull)
