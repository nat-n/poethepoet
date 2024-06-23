import json
from os import environ
from pathlib import Path
from types import MappingProxyType

try:
    import tomllib as tomli
except ImportError:
    import tomli  # type: ignore[no-redef]

from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

from .exceptions import ConfigValidationError, PoeException
from .options import NoValue, PoeOptions

POE_DEBUG = environ.get("POE_DEBUG", "0") == "1"


class ConfigPartition:
    options: PoeOptions
    full_config: Mapping[str, Any]
    poe_options: Mapping[str, Any]
    path: Path
    project_dir: Path
    _cwd: Optional[Path]

    ConfigOptions: Type[PoeOptions]
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


EmptyDict: Mapping = MappingProxyType({})


class ProjectConfig(ConfigPartition):
    is_primary = True

    class ConfigOptions(PoeOptions):
        """
        Options supported directly under tool.poe in the main config i.e. pyproject.toml
        """

        default_task_type: str = "cmd"
        default_array_task_type: str = "sequence"
        default_array_item_task_type: str = "ref"
        env: Mapping[str, str] = EmptyDict
        envfile: Union[str, Sequence[str]] = tuple()
        executor: Mapping[str, str] = MappingProxyType({"type": "auto"})
        include: Sequence[str] = tuple()
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
            # > Union[str, Sequence[str], Mapping[str, str]] => List[dict]
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

            from .executor import PoeExecutor
            from .task.base import PoeTask

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
                    if interpreter not in PoeConfig.KNOWN_SHELL_INTERPRETERS:
                        raise ConfigValidationError(
                            f"Unsupported value {interpreter!r} for option "
                            "'shell_interpreter'\n"
                            f"Expected one of {PoeConfig.KNOWN_SHELL_INTERPRETERS!r}"
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

        env: Mapping[str, str] = EmptyDict
        envfile: Union[str, Sequence[str]] = tuple()
        tasks: Mapping[str, Any] = EmptyDict

        def validate(self):
            """
            Validation rules that don't require any extra context go here.
            """
            super().validate()

            # Apply same validation to env option as for the main config
            ProjectConfig.ConfigOptions.validate_env(self.env)


class PoeConfig:
    _project_config: ProjectConfig
    _included_config: List[IncludedConfig]

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

    """
    The filename to look for when loading config
    """
    _config_name: str = "pyproject.toml"
    """
    The parent directory of the project config file
    """
    _project_dir: Path
    """
    This can be overridden, for example to align with poetry
    """
    _baseline_verbosity: int = 0

    def __init__(
        self,
        cwd: Optional[Union[Path, str]] = None,
        table: Optional[Mapping[str, Any]] = None,
        config_name: str = "pyproject.toml",
    ):
        self._config_name = config_name
        self._project_dir = self._resolve_project_dir(
            Path().resolve() if cwd is None else Path(cwd)
        )
        self._project_config = ProjectConfig(
            {"tool.poe": table or {}}, path=self._project_dir, strict=False
        )
        self._included_config = []

    def lookup_task(
        self, name: str
    ) -> Union[Tuple[Mapping[str, Any], ConfigPartition], Tuple[None, None]]:
        task = self._project_config.get("tasks", {}).get(name, None)
        if task is not None:
            return task, self._project_config

        for include in reversed(self._included_config):
            task = include.get("tasks", {}).get(name, None)
            if task is not None:
                return task, include

        return None, None

    def partitions(self, included_first=True) -> Iterator[ConfigPartition]:
        if not included_first:
            yield self._project_config
        yield from self._included_config
        if included_first:
            yield self._project_config

    @property
    def executor(self) -> Mapping[str, Any]:
        return self._project_config.options.executor

    @property
    def task_names(self) -> Iterator[str]:
        result = list(self._project_config.get("tasks", {}).keys())
        for config_part in self._included_config:
            for task_name in config_part.get("tasks", {}).keys():
                # Don't use a set to dedup because we want to preserve task order
                if task_name not in result:
                    result.append(task_name)
        yield from result

    @property
    def tasks(self) -> Dict[str, Any]:
        result = dict(self._project_config.get("tasks", {}))
        for config in self._included_config:
            for task_name, task_def in config.get("tasks", {}).items():
                if task_name in result:
                    continue
                result[task_name] = task_def
        return result

    @property
    def default_task_type(self) -> str:
        return self._project_config.options.default_task_type

    @property
    def default_array_task_type(self) -> str:
        return self._project_config.options.default_array_task_type

    @property
    def default_array_item_task_type(self) -> str:
        return self._project_config.options.default_array_item_task_type

    @property
    def shell_interpreter(self) -> Tuple[str, ...]:
        raw_value = self._project_config.options.shell_interpreter
        if isinstance(raw_value, list):
            return tuple(raw_value)
        return (raw_value,)

    @property
    def verbosity(self) -> int:
        return self._project_config.get("verbosity", self._baseline_verbosity)

    @property
    def is_poetry_project(self) -> bool:
        return "poetry" in self._project_config.full_config.get("tool", {})

    @property
    def project_dir(self) -> Path:
        return self._project_dir

    def load(self, target_path: Optional[Union[Path, str]] = None, strict: bool = True):
        """
        target_path is the path to a file or directory for loading config
        If strict is false then some errors in the config structure are tolerated
        """

        config_path = self.find_config_file(
            target_path=Path(target_path) if target_path else None,
            search_parent=target_path is None,
        )
        self._project_dir = config_path.parent

        try:
            self._project_config = ProjectConfig(
                self._read_config_file(config_path),
                path=config_path,
                project_dir=self._project_dir,
                strict=strict,
            )
        except KeyError:
            raise PoeException(
                f"No poe configuration found in file at {self._config_name}"
            )
        except ConfigValidationError:
            # Try again to load Config with minimal validation so we can still display
            # the task list alongside the error
            self._project_config = ProjectConfig(
                self._read_config_file(config_path),
                path=config_path,
                project_dir=self._project_dir,
                strict=False,
            )
            raise

        self._load_includes(strict=strict)

    def find_config_file(
        self, target_path: Optional[Path] = None, search_parent: bool = True
    ) -> Path:
        """
        If search_parent is False then check if the target_path points to a config file
        or a directory containing a config file.

        If search_parent is True then also search for the config file in parent
        directories in ascending order.

        If no target_path is provided then start with self._project_dir

        If the given target_path is a file, then it may be named as any toml or json
        file, otherwise the config file name must match `self._config_name`.

        If no config file can be found then raise a PoeException
        """
        if target_path is None:
            target_path = self._project_dir
        else:
            target_path = target_path.resolve()

        if not search_parent:
            if not (
                target_path.name.endswith(".toml") or target_path.name.endswith(".json")
            ):
                target_path = target_path.joinpath(self._config_name)
            if not target_path.exists():
                raise PoeException(
                    f"Poe could not find a {self._config_name!r} file at the given "
                    f"location: {str(target_path)!r}"
                )
            return target_path

        return self._resolve_project_dir(target_path, raise_on_fail=True)

    def _resolve_project_dir(self, target_dir: Path, raise_on_fail: bool = False):
        """
        Look for the self._config_name in the current working directory,
        followed by all parent directories in ascending order.
        Return the path of the parent directory of the first config file found.
        """
        maybe_result = target_dir.joinpath(self._config_name)
        while not maybe_result.exists():
            if len(maybe_result.parents) == 1:
                if raise_on_fail:
                    raise PoeException(
                        f"Poe could not find a {self._config_name!r} file in "
                        f"{target_dir} or any parent directory."
                    )
                else:
                    return target_dir
            maybe_result = maybe_result.parents[1].joinpath(self._config_name).resolve()
        return maybe_result

    def _load_includes(self: "PoeConfig", strict: bool = True):
        # Attempt to load each of the included configs
        for include in self._project_config.options.include:
            include_path = self._resolve_include_path(include["path"])

            if not include_path.exists():
                # TODO: print warning in verbose mode, requires access to ui somehow
                #       Maybe there should be something like a WarningService?

                if POE_DEBUG:
                    print(f" ! Could not include file from invalid path {include_path}")
                continue

            try:
                self._included_config.append(
                    IncludedConfig(
                        self._read_config_file(include_path),
                        path=include_path,
                        project_dir=self._project_dir,
                        cwd=(
                            self.project_dir.joinpath(include["cwd"]).resolve()
                            if include.get("cwd")
                            else None
                        ),
                        strict=strict,
                    )
                )
                if POE_DEBUG:
                    print(f"  Included config from {include_path}")
            except (PoeException, KeyError) as error:
                raise ConfigValidationError(
                    f"Invalid content in included file from {include_path}",
                    filename=str(include_path),
                ) from error

    def _resolve_include_path(self, include_path: str):
        from .env.template import apply_envvars_to_template

        available_vars = {"POE_ROOT": str(self._project_dir)}

        if "${POE_GIT_DIR}" in include_path:
            from .helpers.git import GitRepo

            git_repo = GitRepo(self._project_dir)
            available_vars["POE_GIT_DIR"] = str(git_repo.path or "")

        if "${POE_GIT_ROOT}" in include_path:
            from .helpers.git import GitRepo

            git_repo = GitRepo(self._project_dir)
            available_vars["POE_GIT_ROOT"] = str(git_repo.main_path or "")

        include_path = apply_envvars_to_template(
            include_path, available_vars, require_braces=True
        )

        return self._project_dir.joinpath(include_path).resolve()

    @staticmethod
    def _read_config_file(path: Path) -> Mapping[str, Any]:
        try:
            with path.open("rb") as file:
                if path.suffix.endswith(".json"):
                    return json.load(file)
                else:
                    return tomli.load(file)

        except tomli.TOMLDecodeError as error:
            raise PoeException(f"Couldn't parse toml file at {path}", error) from error

        except json.decoder.JSONDecodeError as error:
            raise PoeException(
                f"Couldn't parse json file from {path}", error
            ) from error

        except Exception as error:
            raise PoeException(f"Couldn't open file at {path}") from error
