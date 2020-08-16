from pathlib import Path
import sys
from typing import Any, IO, MutableMapping, Optional, Sequence, Union
from .config import PoeConfig
from .task import PoeTask
from .ui import PoeUi
from .exceptions import ExecutionError, PoeException


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

        if not self.resolve_task():
            return 1

        return self.run_task() or 0

    def resolve_task(self) -> bool:
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

        self.task = PoeTask.from_config(task_name, config=self.config, ui=self.ui)
        return True

    def run_task(self) -> Optional[int]:
        _, *take_args = self.ui["task"]
        try:
            assert self.task
            return self.task.run(
                take_args,
                project_dir=Path(self.config.project_dir),
                dry=self.ui["dry_run"],
            )
        except PoeException as error:
            self.print_help(error=error)
            return 1
        except ExecutionError as error:
            self.ui.print_error(error=error)
            return 1

    def print_help(
        self,
        info: Optional[str] = None,
        error: Optional[Union[str, PoeException]] = None,
    ):
        if isinstance(error, str):
            error == PoeException(error)
        tasks_help = {
            task: (content.get("help", "") if isinstance(content, dict) else "")
            for task, content in self.config.tasks.items()
        }
        self.ui.print_help(tasks=tasks_help, info=info, error=error)  # type: ignore
