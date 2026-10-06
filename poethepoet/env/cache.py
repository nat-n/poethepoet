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
    _missing_warned: set[str]

    def __init__(self, project_dir: Path, io: PoeIO):
        self._project_dir = project_dir
        self._io = io
        # Paths of missing envfiles already warned about, so that each is only
        # reported once per run even though task envs may be resolved repeatedly
        self._missing_warned = set()

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
                except UnicodeDecodeError as error:
                    raise ExecutionError(
                        f"Envfile at {envfile_path_str!r} could not be decoded as "
                        f"UTF-8 text ({error.reason} at byte {error.start})"
                    ) from error
                except OSError as error:
                    raise ExecutionError(
                        f"Failed to read envfile at {envfile_path_str!r}: "
                        f"{error.strerror or error}"
                    ) from error
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
                if envfile_path_str not in self._missing_warned:
                    self._missing_warned.add(envfile_path_str)
                    self._io.print_warning(
                        f"Poe failed to locate envfile at {envfile_path_str!r}"
                    )
                return {}

        return _resolve_ast(self._ast_cache[envfile_path_str], base_env or {})
