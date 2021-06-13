import os
from pathlib import Path
import sys
from typing import Any, Dict, IO, MutableMapping, Optional, Sequence, Tuple, Union
from .config import PoeConfig
from .context import RunContext
from .exceptions import ExecutionError, PoeException
from .task import PoeTask
from .task.args import PoeTaskArgs
from .task.graph import TaskExecutionGraph
from .ui import PoeUi


class PoeThePoet:
    cwd: Path
    ui: PoeUi
    config: PoeConfig
    task: Optional[PoeTask] = None

    def __init__(
        self,
        cwd: Path,
        config: Optional[MutableMapping[str, Any]] = None,
        output: IO = sys.stdout,
    ):
        self.cwd = cwd
        self.config = PoeConfig(cwd=cwd, table=config)
        self.ui = PoeUi(output=output)

    def __call__(self, cli_args: Sequence[str]) -> int:
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

        if self.ui["help"]:
            self.print_help()
            return 0

        if not self.resolve_task(" ".join(cli_args)):
            return 1

        assert self.task
        if self.task.has_deps():
            return self.run_task_graph() or 0
        else:
            return self.run_task() or 0

    def resolve_task(self, invocation: Sequence[str]) -> bool:
        task = self.ui["task"]
        if not task:
            self.print_help(info="No task specified.")
            return False

        task_name = task[0]
        if task_name not in self.config.tasks:
            self.print_help(error=PoeException(f"Unrecognised task {task_name!r}"),)
            return False

        if task_name.startswith("_"):
            self.print_help(
                error=PoeException(
                    "Tasks prefixed with `_` cannot be executed directly"
                ),
            )
            return False

        self.task = PoeTask.from_config(
            task_name, config=self.config, ui=self.ui, invocation=tuple(invocation)
        )
        return True

    def run_task(self, context: Optional[RunContext] = None) -> Optional[int]:
        _, *extra_args = self.ui["task"]
        if context is None:
            context = RunContext(
                config=self.config,
                ui=self.ui,
                env=os.environ,
                dry=self.ui["dry_run"],
                poe_active=os.environ.get("POE_ACTIVE"),
            )
        try:
            assert self.task
            return self.task.run(context=context, extra_args=extra_args)
        except PoeException as error:
            self.print_help(error=error)
            return 1
        except ExecutionError as error:
            self.ui.print_error(error=error)
            return 1

    def run_task_graph(self, context: Optional[RunContext] = None) -> Optional[int]:
        assert self.task
        graph = TaskExecutionGraph(self.task, self.config)
        plan = graph.get_execution_plan()

        context = RunContext(
            config=self.config,
            ui=self.ui,
            env=os.environ,
            dry=self.ui["dry_run"],
            poe_active=os.environ.get("POE_ACTIVE"),
        )

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

    def print_help(
        self,
        info: Optional[str] = None,
        error: Optional[Union[str, PoeException]] = None,
    ):
        if isinstance(error, str):
            error == PoeException(error)
        tasks_help: Dict[str, Tuple[str, Sequence[Tuple[Tuple[str, ...], str]]]] = {
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
        self.ui.print_help(tasks=tasks_help, info=info, error=error)  # type: ignore
