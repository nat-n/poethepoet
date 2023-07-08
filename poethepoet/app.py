import os
import sys
from pathlib import Path
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    Dict,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from .exceptions import ExecutionError, PoeException

if TYPE_CHECKING:
    from .config import PoeConfig
    from .context import RunContext
    from .task import PoeTask
    from .ui import PoeUi


class PoeThePoet:
    cwd: Path
    ui: "PoeUi"
    config: "PoeConfig"
    task: Optional["PoeTask"] = None

    def __init__(
        self,
        cwd: Path,
        config: Optional[Union[Mapping[str, Any], "PoeConfig"]] = None,
        output: IO = sys.stdout,
        poetry_env_path: Optional[str] = None,
        config_name: str = "pyproject.toml",
        program_name: str = "poe",
    ):
        from .config import PoeConfig
        from .ui import PoeUi

        self.cwd = cwd
        self.config = (
            config
            if isinstance(config, PoeConfig)
            else PoeConfig(cwd=cwd, table=config, config_name=config_name)
        )
        self.ui = PoeUi(output=output, program_name=program_name)
        self._poetry_env_path = poetry_env_path

    def __call__(self, cli_args: Sequence[str], internal: bool = False) -> int:
        """
        :param internal:
            indicates that this is an internal call to run poe, e.g. from a
            plugin hook.
        """

        self.ui.parse_args(cli_args)

        if self.ui["version"]:
            self.ui.print_version()
            return 0

        try:
            self.config.load(self.ui["project_root"])
            self.config.validate()
        except PoeException as error:
            if self.ui["help"]:
                self.print_help()
                return 0
            self.print_help(error=error)
            return 1

        self.ui.set_default_verbosity(self.config.verbosity)

        if self.ui["help"]:
            self.print_help()
            return 0

        if not self.resolve_task(internal):
            return 1

        assert self.task
        if self.task.has_deps():
            return self.run_task_graph() or 0
        else:
            return self.run_task() or 0

    def resolve_task(self, allow_hidden: bool = False) -> bool:
        from .task import PoeTask

        task = tuple(self.ui["task"])
        if not task:
            self.print_help(info="No task specified.")
            return False

        task_name = task[0]
        if task_name not in self.config.tasks:
            self.print_help(error=PoeException(f"Unrecognised task {task_name!r}"))
            return False

        if task_name.startswith("_") and not allow_hidden:
            self.print_help(
                error=PoeException(
                    "Tasks prefixed with `_` cannot be executed directly"
                ),
            )
            return False

        self.task = PoeTask.from_config(
            task_name, config=self.config, ui=self.ui, invocation=task
        )
        return True

    def run_task(self, context: Optional["RunContext"] = None) -> Optional[int]:
        if context is None:
            context = self.get_run_context()
        try:
            assert self.task
            return self.task.run(context=context, extra_args=self.task.invocation[1:])
        except PoeException as error:
            self.print_help(error=error)
            return 1
        except ExecutionError as error:
            self.ui.print_error(error=error)
            return 1

    def run_task_graph(self) -> Optional[int]:
        from .task.graph import TaskExecutionGraph

        assert self.task
        context = self.get_run_context(multistage=True)
        graph = TaskExecutionGraph(self.task, context)
        plan = graph.get_execution_plan()

        for stage in plan:
            for task in stage:
                if task == self.task:
                    # The final sink task gets special treatment
                    return self.run_task(context)

                try:
                    task_result = task.run(
                        context=context, extra_args=task.invocation[1:]
                    )
                    if task_result:
                        raise ExecutionError(
                            f"Task graph aborted after failed task {task.name!r}"
                        )
                except PoeException as error:
                    self.print_help(error=error)
                    return 1
                except ExecutionError as error:
                    self.ui.print_error(error=error)
                    return 1
        return 0

    def get_run_context(self, multistage: bool = False) -> "RunContext":
        from .context import RunContext

        result = RunContext(
            config=self.config,
            ui=self.ui,
            env=os.environ,
            dry=self.ui["dry_run"],
            poe_active=os.environ.get("POE_ACTIVE"),
            multistage=multistage,
        )
        if self._poetry_env_path:
            # This allows the PoetryExecutor to use the venv from poetry directly
            result.exec_cache["poetry_virtualenv"] = self._poetry_env_path
        return result

    def print_help(
        self,
        info: Optional[str] = None,
        error: Optional[Union[str, PoeException]] = None,
    ):
        from .task.args import PoeTaskArgs

        if isinstance(error, str):
            error = PoeException(error)

        tasks_help: Dict[
            str, Tuple[str, Sequence[Tuple[Tuple[str, ...], str, str]]]
        ] = {
            task_name: (
                (
                    content.get("help", ""),
                    PoeTaskArgs.get_help_content(content.get("args")),
                )
                if isinstance(content, dict)
                else ("", tuple())
            )
            for task_name, content in self.config.tasks.items()
        }

        self.ui.print_help(tasks=tasks_help, info=info, error=error)
