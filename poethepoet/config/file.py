from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from ..exceptions import PoeException


class PoeConfigFile:
    path: Path
    _content: Mapping[str, Any] | None = None
    _error: PoeException | None = None
    _valid: bool = False

    def __init__(self, path: Path):
        self.path = path

    @property
    def content(self) -> Mapping[str, Any] | None:
        return self._content

    @property
    def is_valid(self) -> bool:
        return self._valid

    @property
    def error(self) -> PoeException | None:
        return self._error

    @property
    def is_pyproject(self) -> bool:
        return self.path.name == "pyproject.toml"

    def load(self, force: bool = False) -> Mapping | None:
        if force or not self._content:
            try:
                content = self._read_config_file(self.path)
            except PoeException as error:
                self._error = error
                self._valid = False
                return None

            if self.is_pyproject or content.get("tool", {}).get("poe", {}):
                self._content = content
                self._valid = bool(content.get("tool", {}).get("poe", {}))
            else:
                if tool_poe := content.get("tool.poe"):
                    self._content = {"tool": {"poe": tool_poe}}
                else:
                    self._content = {"tool": {"poe": content}}
                self._valid = True

        return self._content

    @classmethod
    def find_config_files(
        cls, target_path: Path, filenames: Sequence[str], search_parent: bool = True
    ) -> Iterator["PoeConfigFile"]:
        """
        Generate a PoeConfigFile for all potential config files starting from the
        target_path in order of precedence.

        If search_parent is False then check if the target_path points to a config file
        or a directory containing a config file.

        If search_parent is True then also search for the config file in parent
        directories in ascending order.

        If the given target_path is a file, then it may be named as any toml, json, or
        yaml file, otherwise the config file name must match one of `filenames`.
        """

        def scan_dir(target_dir: Path):
            for filename in filenames:
                if target_dir.joinpath(filename).exists():
                    yield cls(target_dir.joinpath(filename))

        target_path = target_path.resolve()

        if target_path.is_dir():
            yield from scan_dir(target_path)

            if search_parent:
                parent_path = target_path
                while len(parent_path.parents) > 1:
                    parent_path = parent_path.parent
                    yield from scan_dir(parent_path)

        elif target_path.exists() and target_path.name.endswith(
            (".toml", ".json", ".yaml")
        ):
            yield cls(target_path)

    @staticmethod
    def _read_config_file(path: Path) -> Mapping[str, Any]:
        try:
            if path.suffix.endswith(".json"):
                import json

                try:
                    with path.open("rb") as file:
                        return json.load(file)
                except json.decoder.JSONDecodeError as error:
                    raise PoeException(
                        f"Couldn't parse json file from {path}", error
                    ) from error

            elif path.suffix.endswith(".yaml"):
                import yaml

                try:
                    with path.open("rb") as file:
                        return yaml.safe_load(file)
                except yaml.parser.ParserError as error:
                    raise PoeException(
                        f"Couldn't parse yaml file from {path}", error
                    ) from error

            else:
                try:
                    import tomllib as tomli
                except ImportError:
                    import tomli  # type: ignore[no-redef]

                try:
                    with path.open("rb") as file:
                        return tomli.load(file)
                except tomli.TOMLDecodeError as error:
                    raise PoeException(
                        f"Couldn't parse toml file at {path}", error
                    ) from error

        except Exception as error:
            raise PoeException(f"Couldn't open file at {path}") from error
