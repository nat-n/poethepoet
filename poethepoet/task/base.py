import os
from pathlib import Path
import re
import subprocess
import sys
from typing import (
    Any,
    Dict,
    Iterable,
    MutableMapping,
    Optional,
    Sequence,
    Type,
    Union,
)
from ..ui import PoeUi

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


class MetaPoeTask(type):
    """
    This metaclass makes all decendents of PoeTask (task types) register themselves on
    declaration and validates that they include the expected class attributes.
    """

    def __init__(cls, *args):
        newclass = super().__init__(*args)
        if cls.__name__ == "PoeTask":
            return
        assert isinstance(getattr(cls, "__key__", None), str)
        assert isinstance(getattr(cls, "__options__", None), dict)
        PoeTask._PoeTask__task_types[cls.__key__] = cls


class PoeTask(metaclass=MetaPoeTask):
    name: str
    content: str
    options: Dict[str, Any]

    __options__: Dict[str, Type]
    __base_options: Dict[str, Type] = {"help": str, "env": dict}
    __task_types: Dict[str, Type["PoeTask"]] = {}

    def __init__(self, name: str, content: str, options: Dict[str, Any], ui: PoeUi):
        self.name = name
        self.content = content.strip()
        self.options = options
        self._ui = ui

    @classmethod
    def from_def(
        cls, task_name: str, task_def: TaskDef, ui: PoeUi, default_type: str
    ) -> "PoeTask":
        if isinstance(task_def, str):
            return cls.__task_types[default_type](
                name=task_name, content=task_def, options={}, ui=ui
            )

        task_type_keys = set(task_def.keys()).intersection(cls.__task_types)
        if len(task_type_keys) == 1:
            task_type_key = next(iter(task_type_keys))
            options = dict(task_def)
            content = options.pop(task_type_key)
            return cls.__task_types[task_type_key](
                name=task_name, content=content, options=options, ui=ui,
            )

        # Something is wrong with this task_def
        raise cls.Error(cls.validate_def(task_name, task_def))

    def run(
        self,
        extra_args: Iterable[str],
        project_dir: Path,
        env: Optional[MutableMapping[str, str]] = None,
        set_cwd: bool = False,
        dry: bool = False,
    ):
        """
        Run this task
        """
        if env is None:
            env = dict(os.environ)
        env["POE_ROOT"] = str(project_dir)
        if self.options.get("env"):
            env = dict(env, **self.options["env"])

        if set_cwd:
            previous_wd = os.getcwd()
            os.chdir(project_dir)

        try:
            self._handle_run(list(extra_args), project_dir, env, dry)
        finally:
            if set_cwd:
                os.chdir(previous_wd)

    @staticmethod
    def _resolve_envvars(content: str, env: MutableMapping[str, str]) -> str:
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

    def _execute(
        self, project_dir: Path, cmd: Sequence[str], env: MutableMapping[str, str]
    ):
        if bool(os.environ.get("POETRY_ACTIVE")):
            # Inside poetry shell
            if sys.platform == "win32":
                # On windows
                exe = subprocess.Popen(cmd, env=env)
                exe.communicate()
                return exe.returncode
            else:
                _stop_coverage()
                # Never return...
                return os.execvpe(cmd[0], tuple(cmd), env)
        else:
            # Use the internals of poetry run directly to execute the command
            poetry_env = self._get_poetry_env(project_dir)
            # Ensure the virtualenv site packages are available
            #  + not 100% sure this is correct
            env["PYTHONPATH"] = poetry_env.site_packages
            env["PATH"] = os.pathsep.join([str(poetry_env._bin_dir), env["PATH"]])
            if "PYTHONHOME" in env:
                del env["PYTHONHOME"]
            _stop_coverage()
            return poetry_env.execute(*cmd, env=env)

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
        elif isinstance(task_def, dict):
            task_type_keys = set(task_def.keys()).intersection(cls.__task_types)
            if len(task_type_keys) == 1:
                task_type_key = next(iter(task_type_keys))
                task_type = cls.__task_types[task_type_key]
                if not isinstance(task_def[task_type_key], str):
                    issue = (
                        f"Invalid task: {task_name!r}. {task_type} value must be a "
                        "string"
                    )
                else:
                    for key in set(task_def) - {task_type_key}:
                        expected_type = cls.__base_options.get(
                            key, task_type.__options__.get(key)
                        )
                        if expected_type is None:
                            issue = (
                                f"Invalid task: {task_name!r}. Unrecognised option "
                                f"{key!r} for task of type: {task_type_key}."
                            )
                            break
                        elif not isinstance(task_def[key], expected_type):
                            issue = (
                                f"Invalid task: {task_name!r}. Option {key!r} should "
                                f"have a value of type {expected_type!r}"
                            )
                            break
                    else:
                        if hasattr(task_type, "_validate_task_def"):
                            issue = task_type._validate_task_def(task_def)
            else:
                issue = (
                    f"Invalid task: {task_name!r}. Task definition must include exactly"
                    f" one task key from {set(cls.__task_types)!r}"
                )
        else:
            return None

        if raize:
            raise cls.Error(issue)
        return issue

    @classmethod
    def is_task_type(cls, task_def_key: str) -> bool:
        return task_def_key in cls.__task_types

    @staticmethod
    def _get_poetry_env(project_dir: Path):
        from clikit.io import ConsoleIO
        from poetry.factory import Factory
        from poetry.utils.env import EnvManager

        poetry = Factory().create_poetry(project_dir)
        # TODO: unify ConsoleIO with ui.output
        return EnvManager(poetry).create_venv(ConsoleIO())

    def _handle_run(
        self,
        extra_args: Iterable[str],
        project_dir: Path,
        env: MutableMapping[str, str],
        dry: bool = False,
    ):
        raise NotImplementedError

    @classmethod
    def _validate_task_def(cls, task_def: TaskDef) -> Optional[str]:
        """
        To be overriden by subclasses to check the given task definition for validity
        specific to that task type and return a message describing the first encountered
        issue if any.
        """
        issue = None
        return issue

    def _print_action(self, action: Any, dry: bool):
        """
        Print the action taken by a task just before executing it.
        """
        min_verbosity = -1 if dry else 0
        self._ui.print_msg(f"<hl>Poe =></hl> {action}", min_verbosity)

    class Error(Exception):
        pass


def _stop_coverage():
    if "coverage" in sys.modules:
        # If Coverage is running then it ends here
        from coverage import Coverage

        cov = Coverage.current()
        cov.stop()
        cov.save()
