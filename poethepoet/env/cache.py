from os import environ
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from ..exceptions import ExecutionError

if TYPE_CHECKING:
    from .ui import PoeUi

POE_DEBUG = environ.get("POE_DEBUG", "0") == 1


class EnvFileCache:
    _cache: dict[str, dict[str, str]] = {}
    _ui: Optional["PoeUi"]
    _project_dir: Path

    def __init__(self, project_dir: Path, ui: Optional["PoeUi"]):
        self._project_dir = project_dir
        self._ui = ui

    def get(self, envfile: Union[str, Path]) -> dict[str, str]:
        """
        Parse, cache, and return the environment variables from the envfile at the
        given path. The path is used as the cache key.
        """
        from .parse import parse_env_file

        envfile_path = self._project_dir.joinpath(Path(envfile).expanduser()).absolute()
        envfile_path_str = str(envfile_path)

        if envfile_path_str in self._cache:
            return self._cache[envfile_path_str]

        result = {}

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
