import json
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


class ConfigPartition:
    ConfigOptions: Type[PoeOptions]
    options: PoeOptions
    full_config: Mapping[str, Any]
    poe_options: Mapping[str, Any]
    cwd: Path
    path: Optional[Path]

    is_primary: bool = False

    def __init__(
        self,
        full_config: Mapping[str, Any],
        cwd: Path,
        path: Optional[Path] = None,
        strict: bool = True,
    ):
        self.poe_options: Mapping[str, Any] = (
            full_config["tool"].get("poe", {})
            if "tool" in full_config
            else full_config.get("tool.poe", {})
        )
        self.options = next(self.ConfigOptions.parse(self.poe_options, strict=strict))
        self.full_config = full_config
        self.cwd = cwd
        self.path = path

    def get(self, key: str, default: Any = NoValue):
        return self.options.get(key, default)

    def resolve_paths(self, paths: Union[str, Sequence[str]]) -> Tuple[str]:
        """
        FIXME: what is this meant to be?
        """
        ...


EmptyDict: Mapping = MappingProxyType({})


class ProjectConfig(ConfigPartition):
    is_primary = True

    class ConfigOptions(PoeOptions):
        """
        Options allowed directly under tool.poe in pyproject.toml
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

    _config_name: str
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
        self._project_dir = Path().resolve() if cwd is None else Path(cwd)
        self._project_config = ProjectConfig(
            {"tool.poe": table or {}}, cwd=self._project_dir, strict=False
        )
        self._included_config = []
        self._config_name = config_name

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
        for config_part in self._included_config:
            yield config_part
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
    def tasks(self) -> Mapping[str, Any]:
        result = dict(self._project_config.get("tasks", {}))
        for config in reversed(self._included_config):
            result.update(config.get("tasks", {}))
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
    def global_env(self) -> Dict[str, Union[str, Dict[str, str]]]:
        return self._project_config.get("env")

    @property
    def global_envfile(self) -> Optional[str]:
        return self._project_config.get("envfile", None)

    @property
    def shell_interpreter(self) -> Tuple[str, ...]:
        raw_value = self._project_config.options.shell_interpreter
        if isinstance(raw_value, list):
            return tuple(raw_value)
        return (raw_value,)

    @property
    def verbosity(self) -> int:
        return self._project_config.options.get("verbosity", self._baseline_verbosity)

    @property
    def is_poetry_project(self) -> bool:
        return "poetry" in self._project_config.full_config

    @property
    def project_dir(self) -> Path:
        return self._project_dir

    def load(self, target_dir: Optional[str] = None, strict: bool = True):
        if self._project_config.get("tasks"):
            if not self._included_config:
                self._load_includes(strict=strict)
            return

        config_path = self.find_config_file(target_dir)
        self._project_dir = config_path.parent

        try:
            self._project_config = ProjectConfig(
                self._read_config_file(config_path),
                cwd=self._project_dir,
                path=config_path,
                strict=strict,
            )
        except KeyError:
            raise PoeException(
                f"No poe configuration found in file at {self._config_name}"
            )

        self._load_includes(strict=strict)

    def find_config_file(self, target_dir: Optional[str] = None) -> Path:
        """
        Resolve a path to a self._config_name using one of two strategies:
          1. If target_dir is provided then only look there, (accept path to config file
             or to a directory).
          2. Otherwise look for the self._config_name in the current working directory,
             following by all parent directories in ascending order.

        Both strategies result in an Exception on failure.
        """
        if target_dir:
            target_path = Path(target_dir).resolve()
            if not (
                target_path.name.endswith(".toml") or target_path.name.endswith(".json")
            ):
                target_path = target_path.joinpath(self._config_name)
            if not target_path.exists():
                raise PoeException(
                    f"Poe could not find a {self._config_name} file at the given "
                    f"location: {target_dir}"
                )
            return target_path

        maybe_result = self._project_dir.joinpath(self._config_name)
        while not maybe_result.exists():
            if len(maybe_result.parents) == 1:
                raise PoeException(
                    f"Poe could not find a {self._config_name} file in {self._project_dir} or"
                    " its parents"
                )
            maybe_result = maybe_result.parents[1].joinpath(self._config_name).resolve()
        return maybe_result

    def _load_includes(self: "PoeConfig", strict: bool = True):
        # Attempt to load each of the included configs
        for include in self._project_config.options.include:
            include_path = self._project_dir.joinpath(include["path"]).resolve()

            if not include_path.exists():
                # FIXME: print warning in verbose mode, requires access to ui somehow
                continue

            try:
                self._included_config.append(
                    IncludedConfig(
                        self._read_config_file(include_path),
                        cwd=include.get("cwd", self.project_dir),
                        path=include_path,
                        strict=strict,
                    )
                )
            except (PoeException, KeyError) as error:
                raise ConfigValidationError(
                    f"Invalid content in included file from {include_path}",
                    filename=str(include_path),
                ) from error

    # def _merge_config(self, include_config: "PoeConfig"):  # TODO: DELETE THIS
    #     from .task import PoeTask

    #     ## PROBLEMS ##
    #     # - should include.cwd dictate how we look for envfile??
    #     #   - YES: so we can use the .env from the target project area
    #     #   - NO: because we're working in the root project
    #     #   - OR: envfile should only apply to included tasks??  ...  ??
    #     #       - breaking change... but makes sense?
    #     #       - configurable within included file: global.env global.envfile   <---=
    #     #   - COMPS:
    #     #       - included envfile has can be overridden by envfile from root
    #     #            (explain rationale in docs)
    #     #       - yes only if "cwd=True" in included file (this sounds dumb)
    #     #   - ??
    #     #       - do we also need an option to isolate included tasks from root env??
    #     #           - naaa
    #     # - include.cwd how to keep track of task connection to included config file?
    #     #       - so task can prefer the env from the included config...

    #     """
    #     include.cwd should apply to
    #     - imported tasks
    #     - file level envfiles
    #     - task
    #         - level envfiles
    #         - capture_stdout

    #     task_def, task_inheritance = config.get_task(task_name)

    #     """

    #     # Env is special because it can be extended rather than just overwritten
    #     if include_config.global_env:
    #         self._poe["env"] = {
    #             **include_config.global_env, **self._poe.get("env", {})
    #         }

    #     if include_config.global_envfile and "envfile" not in self._poe:
    #         self._poe[
    #             "envfile"
    #         ] = (
    #               # FIXME: if envfile in root config then included envfile ignored??
    #             include_config.global_envfile
    #         )

    #     # Includes additional tasks with preserved ordering
    #     self._poe["tasks"] = own_tasks = self._poe.get("tasks", {})
    #     for task_name, task_def in include_config.tasks.items():
    #         if task_name in own_tasks:
    #             # don't override tasks from the base config
    #             continue

    #         task_def = PoeTask.normalize_task_def(task_def, include_config)
    #         if include_config.cwd:
    #             # Override the config of each task to use the include level cwd as a
    #             # base for the task level cwd
    #             if "cwd" in task_def:
    #                 # rebase the configured cwd onto the include level cwd
    #                 task_def["cwd"] = str(
    #                     Path(include_config.cwd)
    #                     .resolve()
    #                     .joinpath(task_def["cwd"])
    #                     .relative_to(self.project_dir)
    #                 )
    #             else:
    #                 task_def["cwd"] = str(include_config.cwd)

    #         own_tasks[task_name] = task_def

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
