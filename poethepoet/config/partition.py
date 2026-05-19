from __future__ import annotations

import re
from collections.abc import Mapping, Sequence  # noqa: TC003
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, TypedDict, get_args

from ..exceptions import ConfigValidationError
from ..options import NoValue, PoeOptions
from ..options.annotations import option_annotation, register_type_alias
from .primitives import EmptyDict, EnvDefault

if TYPE_CHECKING:
    from pathlib import Path

    from ..task.base import TaskDef
    from .primitives import EnvfileOption


ShellInterpreter = Literal[
    "posix",
    "sh",
    "bash",
    "zsh",
    "fish",
    "pwsh",  # powershell >= 6
    "powershell",  # any version of powershell
    "python",
]
# Register the alias for the PoeOptions annotation system (the helper returns
# the alias unchanged, but assigning it inline confuses mypy when the name is
# later used as a type annotation in this same module).
register_type_alias("ShellInterpreter", ShellInterpreter)

# Derived from the Literal so the tuple and the type stay in lockstep.
KNOWN_SHELL_INTERPRETERS: tuple[str, ...] = get_args(ShellInterpreter)

_GROUP_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")
"""
Pattern for valid group names. Used by ProjectConfig.ConfigOptions.validate
and (in Phase 2) by the schema generator's groups_map patternProperties.

ASCII-only (no Unicode ``\\w``) so the pattern behaves identically in Python
and in editor-side JSON Schema validators, which use ECMA-262's ASCII-only
``\\w``.
This matches the same convention used by `_TASK_NAME_PATTERN` in task/base.py.

The anchors make the pattern usable with both re.fullmatch and re.match.
"""


@option_annotation
class IncludeScriptItem(TypedDict):
    script: str
    """
    A reference to a Python callable that returns toml or json-like config to be
    merged into the project config.
    """

    cwd: str
    """
    Specify the working directory for resolving relative paths referenced by the
    included script.
    """

    executor: str | dict
    """
    Configure the executor used when invoking the include_script callable.
    """


IncludeScriptItem.__optional_keys__ = frozenset({"cwd", "executor"})


@option_annotation
class IncludeItem(TypedDict):
    path: str
    """
    The path to the toml or json config file to include, relative to the parent
    config file.
    """

    cwd: str
    """
    Specify the working directory for resolving relative paths referenced by the
    included config.
    """

    recursive: bool
    """
    If true, includes declared in the included file will also be loaded.
    """


IncludeItem.__optional_keys__ = frozenset({"cwd", "recursive"})


@option_annotation
class TaskGroup(TypedDict):
    heading: str
    """
    A human-readable name for the group displayed in the help output.
    """

    executor: Mapping[str, str | Sequence[str] | bool] | str | None = None  # type: ignore[misc]
    """
    Configure the executor used by tasks within this group.
    """

    tasks: Mapping[str, Any] = EmptyDict  # type: ignore[misc]
    """
    The tasks defined within this group.
    """


TaskGroup.__optional_keys__ = frozenset({"executor", "tasks"})


class GroupConfig:
    name: str
    heading: str
    executor: dict | None

    def __init__(
        self,
        name: str,
        group_def: dict[str, Any],
    ):
        self.name = name
        heading = group_def.get("heading", name)
        assert isinstance(heading, str)
        self.heading = heading
        executor = group_def.get("executor")
        assert executor is None or isinstance(executor, dict)
        self.executor = executor


class TaskConfig:
    name: str
    task_def: TaskDef
    partition: ConfigPartition
    group: GroupConfig | None

    def __init__(
        self,
        name: str,
        task_def: TaskDef,
        partition: ConfigPartition,
        group: GroupConfig | None = None,
    ):
        self.name = name
        self.task_def = task_def
        self.partition = partition
        self.group = group

    def get(self, key: str, default: Any = None):
        """
        Get task option
        """
        if isinstance(self.task_def, dict):
            return self.task_def.get(key, default)
        return default


class ConfigPartition:
    options: PoeOptions
    full_config: Mapping[str, Any]
    poe_options: Mapping[str, Any]
    path: Path
    _project_dir: Path
    _cwd: Path | None

    ConfigOptions: type[PoeOptions]
    is_primary: bool = False

    def __init__(
        self,
        full_config: Mapping[str, Any],
        path: Path,
        project_dir: Path | None = None,
        cwd: Path | None = None,
        strict: bool = True,
    ):
        self.poe_options: Mapping[str, Any] = (
            full_config["tool"].get("poe", {})
            if "tool" in full_config
            else full_config.get("tool.poe", {})
        )
        self.options = next(
            self.ConfigOptions.parse(
                self.poe_options,
                strict=strict,
                # Allow and standard config keys, even if not declared
                # This avoids misguided validation errors on included config
                extra_keys=tuple(ProjectConfig.ConfigOptions.get_fields()),
            )
        )
        self.full_config = full_config
        self.path = path
        self._cwd = cwd
        self._project_dir = project_dir or self.path.parent

    @property
    def cwd(self):
        return self._cwd or self._project_dir

    @property
    def config_dir(self):
        return self._cwd or self.path.parent

    def get(self, key: str, default: Any = NoValue):
        return self.options.get(key, default)

    def collect_tasks(self, strict: bool = True) -> dict[str, TaskConfig]:
        """
        Collect tasks configured in this partition (including from groups).
        """
        result = {
            task_name: TaskConfig(task_name, task_def, self)
            for task_name, task_def in self.get("tasks", {}).items()
        }

        for group_name, group_def in self.get("groups", {}).items():
            for task_name, task_def in group_def.get("tasks", {}).items():
                if strict and task_name in result:
                    raise ConfigValidationError(
                        f"Config from {self.path} contains task "
                        f"{task_name!r} multiple times, including in group {group_name}"
                    )
                result[task_name] = TaskConfig(
                    task_name, task_def, self, GroupConfig(group_name, group_def)
                )

        return result


class ProjectConfig(ConfigPartition):
    is_primary = True

    class ConfigOptions(PoeOptions):
        """
        Options supported directly under tool.poe in the main config i.e. pyproject.toml
        """

        default_task_type: str = "cmd"
        """
        Sets the default task type for tasks defined as strings. By default, tasks
        are interpreted as shell commands ('cmd'). This can be overridden to
        'script' or other supported types.
        """

        default_array_task_type: str = "sequence"
        """
        When a task is declared as an array (instead of a table), then it is
        interpreted as the default array task type, which will be 'sequence' unless
        otherwise specified.
        """

        default_array_item_task_type: str = "ref"
        """
        When a task is declared as a string inside an array (e.g. inline in a
        sequence task), then it is interpreted as the default array item task type,
        which will be 'ref' unless otherwise specified.
        """

        env: Mapping[str, str | EnvDefault] = EmptyDict
        """
        A map of environment variables to be set for all tasks.
        """

        envfile: str | Sequence[str] | EnvfileOption = ()
        """
        Provide one or more env files to be loaded before running tasks. If an
        array is provided, files will be loaded in the given order.
        """

        executor: Mapping[str, str | Sequence[str] | bool] | str = MappingProxyType(
            {"type": "auto"}
        )
        """
        Configure the executor for running tasks. The type can be 'auto', 'poetry',
        'uv', 'virtualenv', or 'simple', with 'auto' being the default. Some
        executor types accept additional configuration options.
        """

        include: str | Sequence[str | IncludeItem] = ()
        """
        Specify one or more other toml or json files to load tasks from.
        """

        include_script: str | Sequence[str | IncludeScriptItem] = ()
        """
        Load dynamically generated tasks from one or more python functions.
        """

        poetry_command: str = "poe"
        """
        Change the name of the task poe registers with poetry when used as a
        plugin.
        """

        poetry_hooks: Mapping[str, str] = EmptyDict
        """
        Register tasks to run automatically before or after other poetry CLI
        commands.
        """

        shell_interpreter: ShellInterpreter | Sequence[ShellInterpreter] = "posix"
        """
        Change the default shell interpreter for executing shell tasks. Normally,
        tasks are executed using a posix shell, but this can be overridden here.
        """

        verbosity: Literal[-2, -1, 0, 1, 2] = 0
        """
        Sets the default verbosity level for all commands. '-1' is quieter, '0' is
        the default level, and '1' is more verbose. The command line arguments are
        incremental, with '--quiet' or '-q' decreasing verbosity, and '--verbose'
        or '-v' increasing it.
        """

        tasks: Mapping[str, Any] = EmptyDict
        """
        A mapping of task names to task definitions.
        """

        groups: Mapping[str, TaskGroup] = EmptyDict
        """
        Define groups of tasks to be displayed together in the help output.
        """

        @classmethod
        def normalize(
            cls,
            source: Mapping[str, Any] | list[Mapping[str, Any]],
            strict: bool = True,
        ):
            if isinstance(source, list | tuple):
                raise ConfigValidationError("Expected single config")

            config = dict(source)

            # Normalize executor option:
            if (executor := config.get("executor")) and isinstance(executor, str):
                config["executor"] = {"type": executor}

            # Normalize group executor options:
            if groups := config.get("groups"):
                for group_def in groups.values():
                    if isinstance(group_def.get("executor"), str):
                        group_def["executor"] = {"type": group_def["executor"]}

            # > include_script: Union[str, Sequence[str], Sequence[IncludeScriptItem]]
            #       => list[IncludeScriptItem]
            if include_script := config.get("include_script"):
                config["include_script"] = []
                if not isinstance(include_script, list):
                    include_script = [include_script]
                for item in include_script:
                    if isinstance(item, str):
                        config["include_script"].append({"script": item})
                    elif isinstance(executor_config := item.get("executor"), str):
                        config["include_script"].append(
                            {**item, "executor": {"type": executor_config}}
                        )
                    else:
                        config["include_script"].append(item)

            config = _normalize_included_config_path(config)

            yield config

        def validate(self):
            """
            Validation rules that don't require any extra context go here.
            """
            super().validate()

            from ..executor import PoeExecutor
            from ..task.base import PoeTask

            # Validate default_task_type value
            if not PoeTask.is_task_type(self.default_task_type, content_type=str):
                raise ConfigValidationError(
                    "Invalid value for option 'default_task_type': "
                    f"{self.default_task_type!r}\n"
                    f"Expected one of {PoeTask.get_task_types(str)!r}"
                )

            # Validate default_array_task_type value
            if not PoeTask.is_task_type(
                self.default_array_task_type, content_type=list
            ):
                raise ConfigValidationError(
                    "Invalid value for option 'default_array_task_type': "
                    f"{self.default_array_task_type!r}\n"
                    f"Expected one of {PoeTask.get_task_types(list)!r}"
                )

            # Validate default_array_item_task_type value
            if not PoeTask.is_task_type(
                self.default_array_item_task_type, content_type=str
            ):
                raise ConfigValidationError(
                    "Invalid value for option 'default_array_item_task_type': "
                    f"{self.default_array_item_task_type!r}\n"
                    f"Expected one of {PoeTask.get_task_types(str)!r}"
                )

            # Validate default verbosity.
            if self.verbosity < -2 or self.verbosity > 2:
                raise ConfigValidationError(
                    f"Invalid value for option 'verbosity': {self.verbosity!r},\n"
                    "Expected value be between -2 and 2."
                )

            self.validate_env(self.env)

            # Validate executor config
            PoeExecutor.validate_config(self.executor)

            # Validate include_script executor configs
            for include_script in self.include_script:
                if executor := include_script.get("executor"):
                    PoeExecutor.validate_config(executor)

            # Validate group names
            for group_name in self.groups.keys():
                if not _GROUP_NAME_PATTERN.fullmatch(group_name):
                    raise ConfigValidationError(
                        f"Invalid group name {group_name!r}. Group names must contain "
                        "only letters, digits, hyphens, and underscores."
                    )

        @classmethod
        def validate_env(cls, env: Mapping[str, str]):
            # Validate env value
            for key, value in env.items():
                if isinstance(value, dict):
                    if tuple(value.keys()) != ("default",) or not isinstance(
                        value["default"], str
                    ):
                        raise ConfigValidationError(
                            f"Invalid declaration at {key!r} in option 'env': {value!r}"
                        )
                elif not isinstance(value, str):
                    raise ConfigValidationError(
                        f"Value of {key!r} in option 'env' should be a string, "
                        f"but found {type(value).__name__!r}"
                    )


class IncludedConfig(ConfigPartition):
    class ConfigOptions(PoeOptions):
        """
        Options supported directly under tool.poe in included config files
        """

        env: Mapping[str, str | EnvDefault] = EmptyDict
        """
        A map of environment variables to be set for all tasks in the included
        config.
        """

        envfile: str | EnvfileOption | Sequence[str | EnvfileOption] = ()
        """
        Provide one or more env files to be loaded before running tasks from this
        included config. If an array is provided, files will be loaded in the
        given order.
        """

        tasks: Mapping[str, Any] = EmptyDict
        """
        A mapping of task names to task definitions contributed by this included
        config.
        """

        groups: Mapping[str, TaskGroup] = EmptyDict
        """
        Define groups of tasks contributed by this included config.
        """

        include: str | Sequence[str | IncludeItem] = ()
        """
        Specify one or more other toml or json files to load tasks from.
        """

        @classmethod
        def normalize(
            cls,
            source: Mapping[str, Any] | list[Mapping[str, Any]],
            strict: bool = True,
        ):
            if isinstance(source, (list, tuple)):
                raise ConfigValidationError("Expected single config")

            yield _normalize_included_config_path(dict(source))

        def validate(self):
            """
            Validation rules that don't require any extra context go here.
            """
            super().validate()

            # Apply same validation to env option as for the main config
            ProjectConfig.ConfigOptions.validate_env(self.env)


class PackagedConfig(ConfigPartition):
    class ConfigOptions(PoeOptions):
        """
        Options supported directly under tool.poe in config generated by a function call
        """

        env: Mapping[str, str | EnvDefault] = EmptyDict
        """
        A map of environment variables to be set for all tasks in the packaged
        config.
        """

        envfile: str | EnvfileOption | Sequence[str | EnvfileOption] = ()
        """
        Provide one or more env files to be loaded before running tasks from this
        packaged config. If an array is provided, files will be loaded in the
        given order.
        """

        tasks: Mapping[str, Any] = EmptyDict
        """
        A mapping of task names to task definitions contributed by this packaged
        config.
        """

        groups: Mapping[str, TaskGroup] = EmptyDict
        """
        Define groups of tasks contributed by this packaged config.
        """

        def validate(self):
            """
            Validation rules that don't require any extra context go here.
            """
            super().validate()

            # Apply same validation to env option as for the main config
            ProjectConfig.ConfigOptions.validate_env(self.env)


def _normalize_included_config_path(config: dict) -> dict:
    """
    Normalize include options if set:
    > include: Union[str, Sequence[str], Mapping[str, str]] => list[dict]
    """

    if includes := config.get("include"):
        if isinstance(includes, dict | str):
            includes = [includes]
        if isinstance(includes, list):
            config["include"] = [
                {"path": item} if isinstance(item, str) else item for item in includes
            ]

    return config
