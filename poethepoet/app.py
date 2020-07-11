from pathlib import Path
import sys
from typing import Any, IO, MutableMapping, Optional, Sequence, Union
from .config import PoeConfig
from .task import PoeTask
from .ui import PoeUi
from .exceptions import PoeException


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

        self.run_task()
        return 0

    def resolve_task(self) -> bool:
        task = self.ui["task"]
        if not task:
            self.print_help(info="No task specified.")
            return False

        task_name = task[0]
        if task_name not in self.config.tasks:
            self.print_help(error=PoeException(f"Unrecognised task {task_name!r}"),)
            return False

        self.task = PoeTask.from_def(
            task_name,
            self.config.tasks[task_name],
            ui=self.ui,
            default_type=self.config.default_task_type,
        )
        return True

    def run_task(self):
        _, *take_args = self.ui["task"]
        self.task.run(
            take_args,
            project_dir=self.config.project_dir,
            set_cwd=self.config.run_in_project_root,
            dry=self.ui["dry_run"],
        )

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
