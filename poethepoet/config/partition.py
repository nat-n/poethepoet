from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, TypedDict

from ..exceptions import ConfigValidationError
from ..options import NoValue, PoeOptions
from .primitives import EmptyDict, EnvDefault

KNOWN_SHELL_INTERPRETERS = (
    "posix",
    "sh",
    "bash",
    "zsh",
    "fish",
    "pwsh",  # powershell >= 6
    "powershell",  # any version of powershell
    "python",
)


class IncludeScriptItem(TypedDict):
    script: str
    cwd: str
    executor: str | dict


IncludeScriptItem.__optional_keys__ = frozenset({"cwd", "executor"})


class IncludeItem(TypedDict):
    path: str
    cwd: str


IncludeItem.__optional_keys__ = frozenset({"cwd"})


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


class ProjectConfig(ConfigPartition):
    is_primary = True

    class ConfigOptions(PoeOptions):
        """
        Options supported directly under tool.poe in the main config i.e. pyproject.toml
        """

        default_task_type: str = "cmd"
        default_array_task_type: str = "sequence"
        default_array_item_task_type: str = "ref"
        env: Mapping[str, str | EnvDefault] = EmptyDict
        envfile: str | Sequence[str] = ()
        executor: Mapping[str, str | Sequence[str] | bool] | str = MappingProxyType(
            {"type": "auto"}
        )
        include: str | Sequence[str] | Sequence[IncludeItem] = ()
        include_script: str | Sequence[str | IncludeScriptItem] = ()
        poetry_command: str = "poe"
        poetry_hooks: Mapping[str, str] = EmptyDict
        shell_interpreter: str | Sequence[str] = "posix"
        verbosity: Literal[-2, -1, 0, 1, 2] = 0
        tasks: Mapping[str, Any] = EmptyDict

        @classmethod
        def normalize(
            cls,
            config: Any,
            strict: bool = True,
        ):
            if isinstance(config, (list, tuple)):
                raise ConfigValidationError("Expected ")

            # Normalize include option:
            # > Union[str, Sequence[str], Mapping[str, str]] => list[dict]
            if includes := config.get("include"):
                if isinstance(includes, (dict, str)):
                    includes = [includes]
                if isinstance(includes, list):
                    config["include"] = [
                        {"path": item} if isinstance(item, str) else item
                        for item in includes
                    ]

            # Normalize include_script option:
            # > Union[str, Sequence[str], Sequence[IncludeScriptItem]]
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
                            {
                                "script": item["script"],
                                "executor": {"type": executor_config},
                            }
                        )
                    else:
                        config["include_script"].append(item)
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

            # Validate shell_interpreter type
            if self.shell_interpreter:
                shell_interpreter = (
                    (self.shell_interpreter,)
                    if isinstance(self.shell_interpreter, str)
                    else self.shell_interpreter
                )
                for interpreter in shell_interpreter:
                    if interpreter not in KNOWN_SHELL_INTERPRETERS:
                        raise ConfigValidationError(
                            f"Unsupported value {interpreter!r} for option "
                            "'shell_interpreter'\n"
                            f"Expected one of {KNOWN_SHELL_INTERPRETERS!r}"
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
        envfile: str | Sequence[str] = tuple()
        tasks: Mapping[str, Any] = EmptyDict

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
        envfile: str | Sequence[str] = tuple()
        tasks: Mapping[str, Any] = EmptyDict

        def validate(self):
            """
            Validation rules that don't require any extra context go here.
            """
            super().validate()

            # Apply same validation to env option as for the main config
            ProjectConfig.ConfigOptions.validate_env(self.env)
