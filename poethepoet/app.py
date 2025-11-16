from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

from .exceptions import ExecutionError, PoeException
from .helpers.eventloop import run_async

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence

    from .config import PoeConfig
    from .context import RunContext
    from .io import PoeIO
    from .task.base import PoeTask, TaskSpecFactory
    from .ui import PoeUi


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
        poe_tasks.toml poe_tasks.yaml poe_tasks.json
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

        self.cwd = Path(cwd) if cwd else Path().resolve()

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

    async def _call(self, internal: bool = False) -> int:
        should_display_help = self.ui["help"] != Ellipsis

        try:
            await self.config.load(target_path=self.ui["project_root"])
            self.io.configure(baseline=self.config.verbosity)
            for task_spec in self.task_specs.load_all():
                task_spec.validate(self.config, self.task_specs)
        except PoeException as error:
            if should_display_help:
                self.print_help()
                return 0
            self.print_help(error=error)
            return 1

        if should_display_help:
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
        if task_name not in self.config.task_names:
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

    async def _run_task(self, task: PoeTask, context: RunContext | None = None) -> int:
        async with self.run_context(existing=context) as context:
            try:
                task_run = await task.run(context=context)
                await task_run.wait(suppress_errors=False)
                return task_run.return_code or 0
            except ExecutionError as error:
                self.ui.print_error(error=error)
                return 1
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

                    try:
                        task_run = await stage_task.run(context=context)
                        await task_run.wait(suppress_errors=False)
                        if task_run.has_failure:
                            raise ExecutionError(
                                "Task graph aborted after failed task "
                                f"{stage_task.name!r}"
                            )
                    except PoeException as error:
                        self.print_help(error=error)
                        return 1
                    except ExecutionError as error:
                        self.ui.print_error(error=error)
                        return 1
        return 0

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
    ):
        from .task.args import PoeTaskArgs

        if isinstance(error, str):
            error = PoeException(error)

        tasks_help: dict[
            str, tuple[str, Sequence[tuple[tuple[str, ...], str, str]]]
        ] = {
            task_name: (
                (
                    str(content.get("help", "")),
                    PoeTaskArgs.get_help_content(
                        content.get("args"), task_name, suppress_errors=bool(error)
                    ),
                )
                if isinstance(content, dict)
                else ("", ())
            )
            for task_name, content in self.config.tasks.items()
        }

        self.ui.print_help(tasks=tasks_help, info=info, error=error)
