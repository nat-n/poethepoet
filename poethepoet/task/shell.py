import os
from pathlib import Path
import re
from typing import Dict, Iterable, MutableMapping, Optional, Type
from .base import PoeTask, TaskDef

_GLOBCHARS_PATTERN = re.compile(r".*[\*\?\[]")


class ShellTask(PoeTask):
    """
    A task consisting of a reference to a shell command
    """

    __key__ = "shell"
    __options__: Dict[str, Type] = {}

    def _handle_run(
        self,
        extra_args: Iterable[str],
        project_dir: Path,
        env: MutableMapping[str, str],
        dry: bool = False,
    ):
        # TODO: look into making this more windows friendly
        shell = os.environ.get("SHELL", "/bin/bash")
        cmd = (shell, "-c", self.content)
        self._print_action(self.content, dry)
        if dry:
            # Don't actually run anything...
            return
        self._execute(project_dir, cmd, env)

    @classmethod
    def _validate_task_def(cls, task_def: TaskDef) -> Optional[str]:
        """
        Check the given task definition for validity specific to this task type and
        return a message describing the first encountered issue if any.
        """
        issue = None
        return issue
