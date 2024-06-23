from os import environ
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional, Union

from ..exceptions import ExecutionError

if TYPE_CHECKING:
    from .ui import PoeUi

POE_DEBUG = environ.get("POE_DEBUG", "0") == 1


class EnvFileCache:
    _cache: Dict[str, Dict[str, str]] = {}
    _ui: Optional["PoeUi"]
    _project_dir: Path

    def __init__(self, project_dir: Path, ui: Optional["PoeUi"]):
        self._project_dir = project_dir
        self._ui = ui

    def get(self, envfile: Union[str, Path]) -> Dict[str, str]:
        from .parse import parse_env_file

        envfile_path_str = str(envfile)

        if envfile_path_str in self._cache:
            return self._cache[envfile_path_str]

        result = {}

        envfile_path = self._project_dir.joinpath(Path(envfile).expanduser())
        if envfile_path.is_file():
            try:
                with envfile_path.open(encoding="utf-8") as envfile_file:
                    result = parse_env_file(envfile_file.readlines())
                if POE_DEBUG:
                    print(f" + Loaded Envfile from {envfile_path}")
            except ValueError as error:
                message = error.args[0]
                raise ExecutionError(
                    f"Syntax error in referenced envfile: {envfile_path_str!r};"
                    f" {message}"
                ) from error

        else:
            if POE_DEBUG:
                print(f" ! Envfile not found at {envfile_path}")

            if self._ui is not None:
                self._ui.print_msg(
                    f"Warning: Poe failed to locate envfile at {envfile_path_str!r}",
                    verbosity=1,
                )

        self._cache[envfile_path_str] = result
        return result
