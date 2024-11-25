from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any, Optional, TypedDict, Union

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


class IncludeItem(TypedDict):
    path: str
    cwd: str


IncludeItem.__optional_keys__ = frozenset({"cwd"})


class ConfigPartition:
    options: PoeOptions
    full_config: Mapping[str, Any]
    poe_options: Mapping[str, Any]
    path: Path
    project_dir: Path
    _cwd: Optional[Path]

    ConfigOptions: type[PoeOptions]
    is_primary: bool = False

    def __init__(
        self,
        full_config: Mapping[str, Any],
        path: Path,
        project_dir: Optional[Path] = None,
        cwd: Optional[Path] = None,
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
        self.project_dir = project_dir or self.path.parent

    @property
    def cwd(self):
        return self._cwd or self.project_dir

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
        env: Mapping[str, Union[str, EnvDefault]] = EmptyDict
        envfile: Union[str, Sequence[str]] = tuple()
        executor: Mapping[str, str] = MappingProxyType({"type": "auto"})
        include: Union[str, Sequence[str], Sequence[IncludeItem]] = tuple()
        poetry_command: str = "poe"
        poetry_hooks: Mapping[str, str] = EmptyDict
        shell_interpreter: Union[str, Sequence[str]] = "posix"
        verbosity: int = 0
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
            if "include" in config:
                includes: Any = []
                include_option = config.get("include", None)

                if isinstance(include_option, (dict, str)):
                    include_option = [include_option]

                if isinstance(include_option, list):
                    valid_keys = {"path", "cwd"}
                    for include in include_option:
                        if isinstance(include, str):
                            includes.append({"path": include})
                        elif (
                            isinstance(include, dict)
                            and include.get("path")
                            and set(include.keys()) <= valid_keys
                        ):
                            includes.append(include)
                        else:
                            raise ConfigValidationError(
                                f"Invalid item for the include option {include!r}",
                                global_option="include",
                            )
                else:
                    # Something is wrong, let option validation handle it
                    includes = include_option

                config = {**config, "include": includes}

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
            if self.verbosity < -1 or self.verbosity > 2:
                raise ConfigValidationError(
                    f"Invalid value for option 'verbosity': {self.verbosity!r},\n"
                    "Expected value be between -1 and 2."
                )

            self.validate_env(self.env)

            # Validate executor config
            PoeExecutor.validate_config(self.executor)

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

        env: Mapping[str, Union[str, EnvDefault]] = EmptyDict
        envfile: Union[str, Sequence[str]] = tuple()
        tasks: Mapping[str, Any] = EmptyDict

        def validate(self):
            """
            Validation rules that don't require any extra context go here.
            """
            super().validate()

            # Apply same validation to env option as for the main config
            ProjectConfig.ConfigOptions.validate_env(self.env)
