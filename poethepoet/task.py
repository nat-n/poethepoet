from enum import Enum
from glob import glob
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any, Dict, Iterable, Optional, Union

TaskDef = Union[str, Dict[str, Any]]

_TASK_NAME_PATTERN = re.compile(r"^\w[\w\d\-\_\+\:]*$")
_SHELL_VAR_PATTERN = re.compile(r"\$(:?{[\w\d_]+}|[\w\d_]+)")
_GLOBCHARS_PATTERN = re.compile(r".*[\*\?\[]")


class PoeTask:
    type: "PoeTask.Type"
    name: str
    content: str

    def __init__(self, type: "PoeTask.Type", name: str, content: str):
        self.type = type
        self.name = name
        self.content = content

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

        if set_cwd:
            previous_wd = os.getcwd()
            os.chdir(project_dir)

        if self.type == self.Type.COMMAND:
            cmd = self._resolve_command(extra_args, env)

            # TODO: Respect quiet mode
            print("Poe =>", " ".join(cmd))

            if poetry_active:
                # Execute like EnvManager does, but without special path resolution
                if is_windows:
                    exe = subprocess.Popen(cmd, env=env)
                    exe.communicate()
                    return exe.returncode
                else:
                    # Never return...
                    return os.execvpe(cmd[0], cmd, env)
            else:
                # Use the internals of poetry run directly to execute the command
                poetry_env = self._get_poetry_env(project_dir)
                poetry_env.execute(*cmd)

        elif self.type == self.Type.SCRIPT:
            # TODO: support calling python functions
            raise NotImplementedError

        if set_cwd:
            os.chdir(previous_wd)

    def _resolve_command(self, extra_args: Iterable[str], env: Dict[str, str]):
        assert self.type == self.Type.COMMAND
        # Template in ${environmental} $variables from env as if we were in a shell
        cursor = 0
        resolved_parts = []
        for match in _SHELL_VAR_PATTERN.finditer(self.content):
            matched = match.group()
            var_name = matched[2:-1] if matched[1] == "{" else matched[1:]
            var_value = env.get(var_name)
            resolved_parts.append(self.content[cursor : match.start()])
            if var_value is not None:
                resolved_parts.append(var_value)
            cursor = match.end()
        resolved_parts.append(self.content[cursor:])
        # Parse shell command tokens
        cmd_tokens = shlex.split("".join(resolved_parts), comments=True)
        # Resolve any glob pattern paths
        expanded_cmd_tokens = []
        for cmd_token in cmd_tokens:
            if _GLOBCHARS_PATTERN.match(cmd_token):
                # looks like a glob path so resolve it
                expanded_cmd_tokens.extend(glob(cmd_token, recursive=True))
            else:
                expanded_cmd_tokens.append(cmd_token)
        # Finally add the extra_args from the invoking command and we're done
        return (*expanded_cmd_tokens, *extra_args)

    @classmethod
    def from_def(cls, task_name: str, task_def: TaskDef) -> "PoeTask":
        if isinstance(task_def, str):
            return cls(name=task_name, type=cls.Type.COMMAND, content=task_def)
        elif "cmd" in task_def:
            return cls(name=task_name, type=cls.Type.COMMAND, content=task_def["cmd"])
        elif "script" in task_def:
            return cls(name=task_name, type=cls.Type.SCRIPT, content=task_def["script"])
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
        return EnvManager(poetry).create_venv(ConsoleIO())

    class Type(Enum):
        COMMAND = "a shell command"
        SCRIPT = "a python function invocation"

    class Error(Exception):
        pass
