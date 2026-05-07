from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from ..exceptions import ExecutionError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ..helpers.parse.envfile import EnvFile
    from ..io import PoeIO


class EnvFileCache:
    _ast_cache: ClassVar[dict[str, EnvFile]] = {}
    _io: PoeIO
    _project_dir: Path

    def __init__(self, project_dir: Path, io: PoeIO):
        self._project_dir = project_dir
        self._io = io

    def get(
        self,
        envfile: str | Path,
        *,
        optional: bool = False,
        base_env: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """
        Parse (cached), resolve, and return the environment variables from the envfile
        at the given path. The AST is cached by path; resolution is done fresh each
        call so that base_env variables are visible during expansion.
        """
        from .parse import _parse_to_ast, _resolve_ast

        envfile_path = self._project_dir.joinpath(Path(envfile).expanduser()).absolute()
        envfile_path_str = str(envfile_path)

        if envfile_path_str not in self._ast_cache:
            if envfile_path.is_file():
                try:
                    with envfile_path.open(encoding="utf-8") as envfile_file:
                        self._ast_cache[envfile_path_str] = _parse_to_ast(
                            envfile_file.read()
                        )
                    self._io.print_debug(f" + Loaded Envfile from {envfile_path}")
                except ValueError as error:
                    message = error.args[0]
                    raise ExecutionError(
                        f"Syntax error in referenced envfile: {envfile_path_str!r};"
                        f" {message}"
                    ) from error

            elif optional:
                self._io.print_debug(
                    f" - Optional envfile not found at {envfile_path_str!r}"
                )
                return {}

            else:
                self._io.print_warning(
                    f"Poe failed to locate envfile at {envfile_path_str!r}"
                )
                return {}

        return _resolve_ast(self._ast_cache[envfile_path_str], base_env or {})
