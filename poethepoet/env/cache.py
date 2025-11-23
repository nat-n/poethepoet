from pathlib import Path
from typing import TYPE_CHECKING

from ..exceptions import ExecutionError

if TYPE_CHECKING:
    from ..io import PoeIO


class EnvFileCache:
    _cache: dict[str, dict[str, str]] = {}
    _io: "PoeIO"
    _project_dir: Path

    def __init__(self, project_dir: Path, io: "PoeIO"):
        self._project_dir = project_dir
        self._io = io

    def get(self, envfile: str | Path) -> dict[str, str]:
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
                self._io.print_debug(f" + Loaded Envfile from {envfile_path}")
            except ValueError as error:
                message = error.args[0]
                raise ExecutionError(
                    f"Syntax error in referenced envfile: {envfile_path_str!r};"
                    f" {message}"
                ) from error

        else:
            self._io.print_warning(
                f"Poe failed to locate envfile at {envfile_path_str!r}"
            )

        self._cache[envfile_path_str] = result
        return result
