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
_SHELL_VAR_PATTERN = re.compile(
    # Matches shell variable patterns, distinguishing escaped examples (to be ignored)
    # There may be a more direct way to doing this
    r"(?:"
    r"(?:[^\\]|^)(?:\\(?:\\{2})*)\$([\w\d_]+)|"  # $VAR preceded by an odd num of \
    r"(?:[^\\]|^)(?:\\(?:\\{2})*)\$\{([\w\d_]+)\}|"  # ${VAR} preceded by an odd num of \
    r"\$([\w\d_]+)|"  # $VAR
    r"\${([\w\d_]+)}"  # ${VAR}
    r")"
)
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
        dry: bool = False,
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
                self._ui.print_msg(f"<hl>Poe =></hl> {' '.join(cmd)}", -dry)
                if dry:
                    # Don't actually run anything...
                    return
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
                    # Ensure the virtualenv site packages are available
                    #  + not 100% sure this is correct
                    env["PYTHONPATH"] = poetry_env.site_packages
                    env["PATH"] = os.pathsep.join(
                        [str(poetry_env._bin_dir), env["PATH"]]
                    )
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

        Supports escaping of the $ if preceded by an odd number of backslashes, in which
        case the backslash immediately precending the $ is removed. This is an
        intentionally very limited implementation of escaping semantics for the sake of
        usability.
        """
        cursor = 0
        resolved_parts = []
        for match in _SHELL_VAR_PATTERN.finditer(content):
            groups = match.groups()
            # the first two groups match escaped varnames so should be ignored
            var_name = groups[2] or groups[3]
            escaped_var_name = groups[0] or groups[1]
            if var_name:
                var_value = env.get(var_name)
                resolved_parts.append(content[cursor : match.start()])
                cursor = match.end()
                if var_value is not None:
                    resolved_parts.append(var_value)
            elif escaped_var_name:
                # Remove the effective escape char
                resolved_parts.append(content[cursor : match.start()])
                cursor = match.end()
                matched = match.string[match.start() : match.end()]
                if matched[0] == "\\":
                    resolved_parts.append(matched[1:])
                else:
                    resolved_parts.append(matched[0:1] + matched[2:])
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
