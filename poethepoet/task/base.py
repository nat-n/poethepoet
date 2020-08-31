import os
from pathlib import Path
import re
import sys
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    MutableMapping,
    Optional,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)
from ..executor import PoetryExecutor
from ..exceptions import PoeException

if TYPE_CHECKING:
    from ..executor import PoeExecutor
    from ..config import PoeConfig
    from ..ui import PoeUi


TaskDef = Union[str, Dict[str, Any], List[Union[str, Dict[str, Any]]]]

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


TaskContent = Union[str, List[Union[str, Dict[str, Any]]]]


class PoeTask(metaclass=MetaPoeTask):
    name: str
    content: TaskContent
    options: Dict[str, Any]

    __options__: Dict[str, Type] = {}
    __content_type__: Type = str
    __base_options: Dict[str, Type] = {"help": str, "env": dict}
    __task_types: Dict[str, Type["PoeTask"]] = {}

    def __init__(
        self,
        name: str,
        content: TaskContent,
        options: Dict[str, Any],
        ui: "PoeUi",
        config: "PoeConfig",
    ):
        self.name = name
        self.content = content.strip() if isinstance(content, str) else content
        self.options = options
        self._ui = ui
        self._config = config
        self._is_windows = sys.platform == "win32"

    @classmethod
    def from_config(cls, task_name: str, config: "PoeConfig", ui: "PoeUi") -> "PoeTask":
        task_def = config.tasks.get(task_name)
        if not task_def:
            raise PoeException(f"Cannot instantiate unknown task {task_name!r}")
        return cls.from_def(task_def, task_name, config, ui)

    @classmethod
    def from_def(
        cls,
        task_def: TaskDef,
        task_name: str,
        config: "PoeConfig",
        ui: "PoeUi",
        array_item: Union[bool, str] = False,
    ) -> "PoeTask":
        if array_item:
            if isinstance(task_def, str):
                task_type = (
                    array_item
                    if isinstance(array_item, str)
                    else config.default_array_item_task_type
                )
                return cls.__task_types[task_type](
                    name=task_name, content=task_def, options={}, ui=ui, config=config
                )
        else:
            if isinstance(task_def, str):
                return cls.__task_types[config.default_task_type](
                    name=task_name, content=task_def, options={}, ui=ui, config=config
                )
        if isinstance(task_def, list):
            return cls.__task_types[config.default_array_task_type](
                name=task_name, content=task_def, options={}, ui=ui, config=config
            )

        assert isinstance(task_def, dict)
        task_type_keys = set(task_def.keys()).intersection(cls.__task_types)
        if len(task_type_keys) == 1:
            task_type_key = next(iter(task_type_keys))
            options = dict(task_def)
            content = options.pop(task_type_key)
            return cls.__task_types[task_type_key](
                name=task_name, content=content, options=options, ui=ui, config=config
            )

        # Something is wrong with this task_def
        raise cls.Error(cls.validate_def(task_name, task_def, config))

    def run(
        self,
        extra_args: Iterable[str],
        project_dir: Path,
        env: Optional[MutableMapping[str, str]] = None,
        set_cwd: bool = True,
        dry: bool = False,
    ) -> int:
        """
        Run this task
        """
        if env is None:
            env = dict(os.environ)
        env["POE_ROOT"] = str(project_dir)
        env = dict(env, **self._config.global_env)
        if self.options.get("env"):
            env = dict(env, **self.options["env"])
        executor = PoetryExecutor(
            env=env, working_dir=project_dir if set_cwd else None, dry=dry
        )
        return self._handle_run(executor, list(extra_args), project_dir, env, dry)

    def _handle_run(
        self,
        executor: "PoeExecutor",
        extra_args: Iterable[str],
        project_dir: Path,
        env: MutableMapping[str, str],
        dry: bool = False,
    ) -> int:
        """
        _handle_run must be implemented by a subclass and return a single executor result.
        """
        raise NotImplementedError

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

    @classmethod
    def validate_def(
        cls, task_name: str, task_def: TaskDef, config: "PoeConfig"
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
                task_content = task_def[task_type_key]
                task_type = cls.__task_types[task_type_key]
                if not isinstance(task_content, task_type.__content_type__):
                    issue = (
                        f"Invalid task: {task_name!r}. {task_type} value must be a "
                        f"{task_type.__content_type__}"
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
                            issue = task_type._validate_task_def(
                                task_name, task_def, config
                            )
            else:
                issue = (
                    f"Invalid task: {task_name!r}. Task definition must include exactly"
                    f" one task key from {set(cls.__task_types)!r}"
                )
        else:
            return None

        return issue

    @classmethod
    def is_task_type(
        cls, task_def_key: str, content_type: Optional[Type] = None
    ) -> bool:
        """
        Checks whether the given key identified a known task type.
        Optionally also check whether the given content_type matches the type of content
        for this tasks type.
        """
        return task_def_key in cls.__task_types and (
            content_type is None
            or cls.__task_types[task_def_key].__content_type__ is content_type
        )

    @classmethod
    def get_task_types(cls, content_type: Optional[Type] = None) -> Tuple[str, ...]:
        if content_type:
            return tuple(
                task_type
                for task_type, task_cls in cls.__task_types.items()
                if task_cls.__content_type__ is content_type
            )
        return tuple(task_type for task_type in cls.__task_types.keys())

    @classmethod
    def _validate_task_def(
        cls, task_name: str, task_def: Dict[str, Any], config: "PoeConfig"
    ) -> Optional[str]:
        """
        To be overriden by subclasses to check the given task definition for validity
        specific to that task type and return a message describing the first encountered
        issue if any.
        """
        issue = None
        return issue

    def _print_action(self, action: str, dry: bool):
        """
        Print the action taken by a task just before executing it.
        """
        min_verbosity = -1 if dry else 0
        self._ui.print_msg(f"<hl>Poe =></hl> <action>{action}</action>", min_verbosity)

    class Error(Exception):
        pass
