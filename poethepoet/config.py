from pathlib import Path
import tomli
from typing import Any, Dict, Mapping, Optional, Union
from .exceptions import PoeException


class PoeConfig:
    _table: Mapping[str, Any]

    TOML_NAME = "pyproject.toml"

    # Options allowed directly under tool.poe in pyproject.toml
    __options__ = {
        "default_task_type": str,
        "default_array_task_type": str,
        "default_array_item_task_type": str,
        "env": dict,
        "envfile": str,
        "executor": dict,
        "verbosity": int,
    }

    def __init__(
        self,
        cwd: Optional[Union[Path, str]] = None,
        table: Optional[Mapping[str, Any]] = None,
    ):
        self.cwd = Path(".").resolve() if cwd is None else Path(cwd)
        self._poe = {} if table is None else table
        self._project_dir: Optional[Path] = None

    @property
    def executor(self) -> Mapping[str, Any]:
        return self._poe.get("executor", {"type": "auto"})

    @property
    def tasks(self) -> Mapping[str, Any]:
        return self._poe.get("tasks", {})

    @property
    def default_task_type(self) -> str:
        return self._poe.get("default_task_type", "cmd")

    @property
    def default_array_task_type(self) -> str:
        return self._poe.get("default_array_task_type", "sequence")

    @property
    def default_array_item_task_type(self) -> str:
        return self._poe.get("default_array_item_task_type", "ref")

    @property
    def global_env(self) -> Dict[str, Union[str, Dict[str, str]]]:
        return self._poe.get("env", {})

    @property
    def global_envfile(self) -> Optional[str]:
        return self._poe.get("envfile")

    @property
    def verbosity(self) -> int:
        return self._poe.get("verbosity", 0)

    @property
    def project(self) -> Any:
        return self._project

    @property
    def project_dir(self) -> str:
        return str(self._project_dir or self.cwd)

    def load(self, target_dir: Optional[str] = None):
        if self._poe:
            raise PoeException("Cannot load poetry config more than once!")
        config_path = self.find_pyproject_toml(target_dir)
        try:
            self._project = self._read_pyproject(config_path)
            self._poe = self._project["tool"]["poe"]
        except KeyError as error:
            raise PoeException(
                f"No poe configuration found in file at {self.TOML_NAME}"
            )
        self._project_dir = config_path.parent

    def validate(self):
        from .task import PoeTask
        from .executor import PoeExecutor

        # Validate keys
        supported_keys = {"tasks", *self.__options__}
        unsupported_keys = set(self._poe) - supported_keys
        if unsupported_keys:
            raise PoeException(f"Unsupported keys in poe config: {unsupported_keys!r}")
        # Validate types of option values
        for key, option_type in self.__options__.items():
            if key in self._poe and not isinstance(self._poe[key], option_type):
                raise PoeException(
                    f"Unsupported value for option {key!r}, expected type to be "
                    f"{option_type.__name__}."
                )
        # Validate executor config
        error = PoeExecutor.validate_config(self.executor)
        if error:
            raise PoeException(error)
        # Validate default_task_type value
        if not PoeTask.is_task_type(self.default_task_type, content_type=str):
            raise PoeException(
                "Unsupported value for option `default_task_type` "
                f"{self.default_task_type!r}"
            )
        # Validate default_array_task_type value
        if not PoeTask.is_task_type(self.default_array_task_type, content_type=list):
            raise PoeException(
                "Unsupported value for option `default_array_task_type` "
                f"{self.default_array_task_type!r}"
            )
        # Validate default_array_item_task_type value
        if not PoeTask.is_task_type(self.default_array_item_task_type):
            raise PoeException(
                "Unsupported value for option `default_array_item_task_type` "
                f"{self.default_array_item_task_type!r}"
            )
        # Validate env value
        for key, value in self.global_env.items():
            if isinstance(value, dict):
                if tuple(value.keys()) != ("default",) or not isinstance(
                    value["default"], str
                ):
                    raise PoeException(
                        f"Invalid declaration at {key!r} in option `env`: {value!r}"
                    )
            elif not isinstance(value, str):
                raise PoeException(
                    f"Value of {key!r} in option `env` should be a string, but found {type(value)!r}"
                )
        # Validate tasks
        for task_name, task_def in self.tasks.items():
            error = PoeTask.validate_def(task_name, task_def, self)
            if error is None:
                continue
            raise PoeException(error)
        # Validate default verbosity.
        if self.verbosity < -1 or self.verbosity > 1:
            raise PoeException(
                f"Invalid value for option `verbosity`: {self.verbosity!r}. Should be between -1 and 1."
            )

    def find_pyproject_toml(self, target_dir: Optional[str] = None) -> Path:
        """
        Resolve a path to a pyproject.toml using one of two strategies:
          1. If target_dir is provided then only look there, (accept path to .toml file
             or to a directory dir).
          2. Otherwise look for the pyproject.toml is the current working directory,
             following by all parent directories in ascending order.

        Both strategies result in an Exception on failure.
        """
        if target_dir:
            target_path = Path(target_dir).resolve()
            if not target_path.name.endswith(".toml"):
                target_path = target_path.joinpath(self.TOML_NAME)
            if not target_path.exists():
                raise PoeException(
                    "Poe could not find a pyproject.toml file at the given location: "
                    f"{target_dir}"
                )
            return target_path

        maybe_result = self.cwd.joinpath(self.TOML_NAME)
        while not maybe_result.exists():
            if maybe_result.parent == Path("/"):
                raise PoeException(
                    f"Poe could not find a pyproject.toml file in {self.cwd} or"
                    " its parents"
                )
            maybe_result = maybe_result.parents[1].joinpath(self.TOML_NAME).resolve()
        return maybe_result

    @staticmethod
    def _read_pyproject(path: Path) -> Mapping[str, Any]:
        try:
            with path.open(encoding="utf-8") as pyproj:
                return tomli.load(pyproj)
        except tomli.TOMLDecodeError as error:
            raise PoeException(f"Couldn't parse toml file at {path}", error) from error
        except Exception as error:
            raise PoeException(f"Couldn't open file at {path}") from error
