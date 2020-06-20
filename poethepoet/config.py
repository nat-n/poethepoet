from pathlib import Path
import toml
from typing import Any, Mapping, Optional, Union
from .exceptions import PoeException
from .task import PoeTask


class PoeConfig:
    _table: Mapping[str, Any]

    TOML_NAME = "pyproject.toml"

    # Options allowed directly under tool.poe in pyproject.toml
    __options__ = {"default_task_type": str, "run_in_project_root": bool}

    def __init__(
        self,
        cwd: Optional[Union[Path, str]] = None,
        table: Optional[Mapping[str, Any]] = None,
    ):
        self.cwd = Path(".").resolve() if cwd is None else Path(cwd)
        self._table = {} if table is None else table
        self._target_dir: Optional[Path] = None

    @property
    def tasks(self) -> Mapping[str, Any]:
        return self._table.get("tasks", {})

    @property
    def run_in_project_root(self) -> bool:
        return self._table.get("run_in_project_root", True)

    @property
    def default_task_type(self) -> str:
        return self._table.get("default_task_type", "cmd")

    @property
    def project_dir(self) -> str:
        return str(self._target_dir or self.cwd)

    def load(self, target_dir: Optional[str] = None, force: bool = False):
        if self._table and not force:
            if target_dir and not self._target_dir:
                self._target_dir = Path(target_dir)
            return
        config_path = self.find_pyproject_toml(target_dir)
        try:
            self._table = self._read_pyproject(config_path)["tool"]["poe"]
        except KeyError as error:
            raise PoeException(
                f"No poe configuration found in file at {self.TOML_NAME}"
            )
        self._target_dir = config_path.parent

    def validate(self):
        # Validate keys
        supported_keys = {"tasks", *self.__options__}
        unsupported_keys = set(self._table) - supported_keys
        if unsupported_keys:
            raise PoeException(f"Unsupported keys in poe config: {unsupported_keys!r}")
        # Validate types of option values
        for key, option_type in self.__options__.items():
            if key in self._table and not isinstance(self._table[key], option_type):
                raise PoeException(
                    f"Unsupported value for option {key!r}, expected type to be "
                    f"{option_type.__name__}."
                )
        # Validate default_task_type value
        if not PoeTask.is_task_type(self.default_task_type):
            # TODO: maybe revisit this if/when not all task types have str content!
            raise PoeException(
                "Unsupported value for option `default_task_type` "
                f"{self.default_task_type!r}"
            )
        # Validate tasks
        for task_name, task_def in self.tasks.items():
            error = PoeTask.validate_def(task_name, task_def)
            if error is None:
                continue
            raise PoeException(error)

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
            with open(path.resolve(), "r") as prproj:
                return toml.load(prproj)
        except toml.TomlDecodeError as error:
            raise PoeException(f"Couldn't parse toml file at {path}", error) from error
        except Exception as error:
            raise PoeException(f"Couldn't open file at {path}") from error
