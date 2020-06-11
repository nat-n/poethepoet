from enum import Enum
from glob import glob
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any, Dict, Iterable, Optional, Union
from .ui import PoeUi

TaskDef = Union[str, Dict[str, Any]]

_TASK_NAME_PATTERN = re.compile(r"^\w[\w\d\-\_\+\:]*$")
_SHELL_VAR_PATTERN = re.compile(r"\$(:?{[\w\d_]+}|[\w\d_]+)")
_GLOBCHARS_PATTERN = re.compile(r".*[\*\?\[]")


class PoeTask:
    type: "PoeTask.Type"
    name: str
    content: str

    def __init__(self, type: "PoeTask.Type", name: str, content: str, ui: PoeUi):
        self.type = type
        self.name = name
        self.content = content
        self._ui = ui

    def run(
        self,
        extra_args: Iterable[str],
        project_dir: Path,
        env: Optional[Dict[str, str]] = None,
        set_cwd: bool = False,
    ):
        """
        Run this task
        """
        is_windows = sys.platform == "win32"
        poetry_active = bool(os.environ.get("POETRY_ACTIVE"))
        if env is None:
            env = dict(os.environ)
        env["POE_ROOT"] = str(project_dir)

        if set_cwd:
            previous_wd = os.getcwd()
            os.chdir(project_dir)

        try:
            if self.type == self.Type.COMMAND:
                cmd = self._resolve_command(extra_args, env)

                # TODO: Respect quiet mode
                self._ui.print_msg(f"<hl>Poe =></hl> {' '.join(cmd)}")

                if poetry_active:
                    if is_windows:
                        exe = subprocess.Popen(cmd, env=env)
                        exe.communicate()
                        return exe.returncode
                    else:
                        _stop_coverage()
                        # Never return...
                        return os.execvpe(cmd[0], cmd, env)
                else:
                    # Use the internals of poetry run directly to execute the command
                    poetry_env = self._get_poetry_env(project_dir)
                    _stop_coverage()
                    return poetry_env.execute(*cmd, env=env)

            elif self.type == self.Type.SCRIPT:
                # TODO: support calling python functions
                raise NotImplementedError
        finally:
            if set_cwd:
                os.chdir(previous_wd)

    def _resolve_command(self, extra_args: Iterable[str], env: Dict[str, str]):
        assert self.type == self.Type.COMMAND
        # Parse shell command tokens
        cmd_tokens = shlex.split(
            self._resolve_envvars(self.content, env), comments=True
        )
        extra_args = [self._resolve_envvars(token, env) for token in extra_args]
        # Resolve any glob pattern paths
        result = []
        for cmd_token in (*cmd_tokens, *extra_args):
            if _GLOBCHARS_PATTERN.match(cmd_token):
                # looks like a glob path so resolve it
                result.extend(glob(cmd_token, recursive=True))
            else:
                result.append(cmd_token)
        # Finally add the extra_args from the invoking command and we're done
        return result

    @staticmethod
    def _resolve_envvars(content: str, env: Dict[str, str]) -> str:
        """
        Template in ${environmental} $variables from env as if we were in a shell
        """
        cursor = 0
        resolved_parts = []
        for match in _SHELL_VAR_PATTERN.finditer(content):
            matched = match.group()
            var_name = matched[2:-1] if matched[1] == "{" else matched[1:]
            var_value = env.get(var_name)
            resolved_parts.append(content[cursor : match.start()])
            if var_value is not None:
                resolved_parts.append(var_value)
            cursor = match.end()
        resolved_parts.append(content[cursor:])
        return "".join(resolved_parts)

    @classmethod
    def from_def(cls, task_name: str, task_def: TaskDef, ui: PoeUi) -> "PoeTask":
        if isinstance(task_def, str):
            return cls(name=task_name, type=cls.Type.COMMAND, content=task_def, ui=ui)
        elif "cmd" in task_def:
            return cls(
                name=task_name, type=cls.Type.COMMAND, content=task_def["cmd"], ui=ui,
            )
        elif "script" in task_def:
            return cls(
                name=task_name, type=cls.Type.SCRIPT, content=task_def["script"], ui=ui,
            )
        # Something is wrong with this task_def
        raise cls.Error(cls.validate_def(task_name, task_def))

    @classmethod
    def validate_def(
        cls, task_name: str, task_def: TaskDef, raize=False
    ) -> Optional[str]:
        """
        Check the given task name and definition for validity and return a message
        describing the first encountered issue if any.
        If raize is True then the issue is raised as an exception.
        """
        issue = None
        if not (task_name[0].isalpha() or task_name[0] == "_"):
            issue = (
                f"Invalid task name: {task_name!r}. Task names must start with a letter"
                " or underscore."
            )
        elif not _TASK_NAME_PATTERN.match(task_name):
            issue = (
                f"Invalid task name: {task_name!r}. Task names characters must be "
                "alphanumeric, colon, underscore or dash."
            )
        elif not isinstance(task_def, str):
            issue = f"Invalid task: {task_name!r}. Task content must be a string."
        else:
            return None

        if raize:
            raise cls.Error(issue)
        return issue

    @staticmethod
    def _get_poetry_env(project_dir: Path):
        from clikit.io import ConsoleIO
        from poetry.factory import Factory
        from poetry.utils.env import EnvManager

        poetry = Factory().create_poetry(project_dir)
        # TODO: unify ConsoleIO with ui.output
        return EnvManager(poetry).create_venv(ConsoleIO())

    class Type(Enum):
        COMMAND = "a shell command"
        SCRIPT = "a python function invocation"

    class Error(Exception):
        pass


def _stop_coverage():
    if "coverage" in sys.modules:
        # If Coverage is running then it ends here
        from coverage import Coverage

        cov = Coverage.current()
        cov.stop()
        cov.save()
