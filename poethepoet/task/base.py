import re
import shlex
import sys
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    MutableMapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)
from .args import PoeTaskArgs
from ..exceptions import PoeException
from ..helpers import is_valid_env_var

if TYPE_CHECKING:
    from ..context import RunContext
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
    __base_options: Dict[str, Union[Type, Tuple[Type, ...]]] = {
        "args": (dict, list),
        "capture_stdout": (str),
        "deps": list,
        "env": dict,
        "envfile": str,
        "executor": dict,
        "help": str,
        "uses": dict,
    }
    __task_types: Dict[str, Type["PoeTask"]] = {}

    def __init__(
        self,
        name: str,
        content: TaskContent,
        options: Dict[str, Any],
        ui: "PoeUi",
        config: "PoeConfig",
        invocation: Tuple[str, ...],
        capture_stdout: bool = False,
    ):
        self.name = name
        self.content = content.strip() if isinstance(content, str) else content
        if capture_stdout:
            self.options = dict(options, capture_stdout=True)
        else:
            self.options = options
        self._ui = ui
        self._config = config
        self._is_windows = sys.platform == "win32"
        self.invocation = invocation

    @classmethod
    def from_config(
        cls,
        task_name: str,
        config: "PoeConfig",
        ui: "PoeUi",
        invocation: Tuple[str, ...],
        capture_stdout: Optional[bool] = None,
    ) -> "PoeTask":
        task_def = config.tasks.get(task_name)
        if not task_def:
            raise PoeException(f"Cannot instantiate unknown task {task_name!r}")
        return cls.from_def(
            task_def,
            task_name,
            config,
            ui,
            invocation=invocation,
            capture_stdout=capture_stdout,
        )

    @classmethod
    def from_def(
        cls,
        task_def: TaskDef,
        task_name: str,
        config: "PoeConfig",
        ui: "PoeUi",
        invocation: Tuple[str, ...],
        array_item: Union[bool, str] = False,
        capture_stdout: Optional[bool] = None,
    ) -> "PoeTask":
        task_type = cls.resolve_task_type(task_def, config, array_item)
        if task_type is None:
            # Something is wrong with this task_def
            raise cls.Error(cls.validate_def(task_name, task_def, config))

        options: Dict[str, Any] = {}
        if capture_stdout is not None:
            # Override config because we want to specifically capture the stdout of this
            # task for internal use
            options["capture_stdout"] = capture_stdout

        if isinstance(task_def, (str, list)):
            return cls.__task_types[task_type](
                name=task_name,
                content=task_def,
                options=options,
                ui=ui,
                config=config,
                invocation=invocation,
            )

        assert isinstance(task_def, dict)
        options = dict(task_def, **options)
        content = options.pop(task_type)
        return cls.__task_types[task_type](
            name=task_name,
            content=content,
            options=options,
            ui=ui,
            config=config,
            invocation=invocation,
        )

    @classmethod
    def resolve_task_type(
        cls,
        task_def: TaskDef,
        config: "PoeConfig",
        array_item: Union[bool, str] = False,
    ) -> Optional[str]:
        if isinstance(task_def, str):
            if array_item:
                return (
                    array_item
                    if isinstance(array_item, str)
                    else config.default_array_item_task_type
                )
            else:
                return config.default_task_type

        elif isinstance(task_def, list):
            return config.default_array_task_type

        elif isinstance(task_def, dict):
            task_type_keys = set(task_def.keys()).intersection(cls.__task_types)
            if len(task_type_keys) == 1:
                return next(iter(task_type_keys))

        return None

    def run(
        self,
        context: "RunContext",
        extra_args: Sequence[str] = tuple(),
        env: Optional[MutableMapping[str, str]] = None,
    ) -> int:
        """
        Run this task
        """
        return self._handle_run(context, extra_args, self._build_env(env, context))

    def _build_env(
        self, env: Optional[MutableMapping[str, str]], context: "RunContext",
    ):
        env = context.get_env(env or {})

        # Get env vars from envfile referenced in global options
        if self._config.global_envfile is not None:
            env.update(context.get_env_file(self._config.global_envfile))

        # Get env vars from global options
        self._update_env(env, self._config.global_env)

        # Get env vars from envfile referenced in task options
        if self.options.get("envfile"):
            env.update(context.get_env_file(self.options["envfile"]))

        # Get env vars from task options
        self._update_env(env, self.options.get("env", {}))

        # Get env vars from dependencies
        env.update(self.get_dep_values(context))

        return env

    @staticmethod
    def _update_env(
        env: Dict[str, str], extra_vars: Dict[str, Union[str, Dict[str, str]]]
    ):
        """
        Update the given env with the given extra_vars. If a value in extra_vars is
        indicated as `default` then only copy it over if that key is not already set on
        env.
        """
        for key, value in extra_vars.items():
            if isinstance(value, str):
                env[key] = value
            elif key not in env:
                env[key] = value["default"]

    def parse_named_args(self, extra_args: Sequence[str]) -> Optional[Dict[str, str]]:
        args_def = self.options.get("args")
        if args_def:
            return PoeTaskArgs(args_def).parse(extra_args)
        return None

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: MutableMapping[str, str],
    ) -> int:
        """
        _handle_run must be implemented by a subclass and return a single executor
        result.
        """
        raise NotImplementedError

    def iter_upstream_tasks(self) -> Iterator[Tuple[str, "PoeTask"]]:
        for task_ref in self.options.get("deps", tuple()):
            yield ("", self._instantiate_dep(task_ref, capture_stdout=False))
        for key, task_ref in self.options.get("uses", {}).items():
            yield (key, self._instantiate_dep(task_ref, capture_stdout=True))

    def get_upstream_invocations(self) -> Set[Tuple[str, ...]]:
        """
        Get identifiers (i.e. invocation tuples) for all upstream tasks
        """
        result = set()
        for task_ref in self.options.get("deps", {}):
            result.add(tuple(shlex.split(task_ref)))
        for task_ref in self.options.get("uses", {}).values():
            result.add(tuple(shlex.split(task_ref)))
        return result

    def get_dep_values(self, context: "RunContext") -> Dict[str, str]:
        """
        Get env vars from upstream tasks declared via the uses option
        """
        return {
            var: context.captured_stdout[tuple(shlex.split(dep))]
            for var, dep in self.options.get("uses", {}).items()
        }

    def has_deps(self) -> bool:
        return bool(self.options.get("deps", False) or self.options.get("uses", False))

    def _instantiate_dep(self, task_ref: str, capture_stdout: bool) -> "PoeTask":
        invocation = tuple(shlex.split(task_ref))
        return self.from_config(
            invocation[0],
            config=self._config,
            ui=self._ui,
            invocation=invocation,
            capture_stdout=capture_stdout,
        )

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
        """
        if not (task_name[0].isalpha() or task_name[0] == "_"):
            return (
                f"Invalid task name: {task_name!r}. Task names must start with a letter"
                " or underscore."
            )
        elif not _TASK_NAME_PATTERN.match(task_name):
            return (
                f"Invalid task name: {task_name!r}. Task names characters must be "
                "alphanumeric, colon, underscore or dash."
            )
        elif isinstance(task_def, dict):
            task_type_keys = set(task_def.keys()).intersection(cls.__task_types)
            if len(task_type_keys) != 1:
                return (
                    f"Invalid task: {task_name!r}. Task definition must include exactly"
                    f" one task key from {set(cls.__task_types)!r}"
                )
            task_type_key = next(iter(task_type_keys))
            task_content = task_def[task_type_key]
            task_type = cls.__task_types[task_type_key]
            if not isinstance(task_content, task_type.__content_type__):
                return (
                    f"Invalid task: {task_name!r}. {task_type} value must be a "
                    f"{task_type.__content_type__}"
                )
            else:
                for key in set(task_def) - {task_type_key}:
                    expected_type = cls.__base_options.get(
                        key, task_type.__options__.get(key)
                    )
                    if expected_type is None:
                        return (
                            f"Invalid task: {task_name!r}. Unrecognised option "
                            f"{key!r} for task of type: {task_type_key}."
                        )
                    elif not isinstance(task_def[key], expected_type):
                        return (
                            f"Invalid task: {task_name!r}. Option {key!r} should "
                            f"have a value of type {expected_type!r}"
                        )
                else:
                    if hasattr(task_type, "_validate_task_def"):
                        task_type_issue = task_type._validate_task_def(
                            task_name, task_def, config
                        )
                        if task_type_issue:
                            return task_type_issue

            if "args" in task_def:
                return PoeTaskArgs.validate_def(task_name, task_def["args"])

            if "\n" in task_def.get("help", ""):
                return (
                    f"Invalid task: {task_name!r}. Help messages cannot contain "
                    "line breaks"
                )

            all_task_names = set(config.tasks)

            if "deps" in task_def:
                for dep in task_def["deps"]:
                    dep_task_name = dep.split(" ", 1)[0]
                    if dep_task_name not in all_task_names:
                        return (
                            f"Invalid task: {task_name!r}. deps options contains "
                            f"reference to unknown task: {dep_task_name!r}"
                        )

            if "uses" in task_def:
                for key, dep in task_def["uses"].items():
                    if not is_valid_env_var(key):
                        return (
                            f"Invalid task: {task_name!r} uses options contains invalid"
                            f" key: {key!r}"
                        )
                    dep_task_name = dep.split(" ", 1)[0]
                    if dep_task_name not in all_task_names:
                        return (
                            f"Invalid task: {task_name!r}. uses options contains "
                            f"reference to unknown task: {dep_task_name!r}"
                        )

        return None

    @classmethod
    def is_task_type(
        cls, task_def_key: str, content_type: Optional[Type] = None
    ) -> bool:
        """
        Checks whether the given key identifies a known task type.
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
