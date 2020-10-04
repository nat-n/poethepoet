import os
from pathlib import Path
import sys
from typing import Dict, MutableMapping


class Virtualenv:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self._is_windows = sys.platform == "win32"

    def exists(self) -> bool:
        """
        Check if the configured path points to a directory
        """
        return self.path.is_dir()

    def bin_dir(self) -> Path:
        """
        Path to where the directory for installed executables should be
        """
        if self._is_windows:
            return self.path.joinpath("Scripts")
        return self.path.joinpath("bin")

    def resolve_executable(self, executable: str) -> str:
        """
        If the given executable can be found in the bin_dir then return its absolute path
        """
        bin_dir = self.bin_dir()
        if bin_dir.joinpath(executable).is_file():
            return str(bin_dir.joinpath(executable))
        if (
            self._is_windows
            and not executable.endswith(".exe")
            and bin_dir.joinpath(f"{executable}.exe").is_file()
        ):
            return str(bin_dir.joinpath(f"{executable}.exe"))
        return executable

    @staticmethod
    def detect(parent_dir: Path) -> bool:
        """
        Check whether there seems to be a valid virtualenv within the given directory at
        either ./venv, or ./.venv
        """
        return (
            Virtualenv(parent_dir.joinpath("venv")).valid()
            or Virtualenv(parent_dir.joinpath(".venv")).valid()
        )

    def valid(self) -> bool:
        """
        Check that the path points to a dir that really is a virtualenv with reasonable
        certainty
        """
        if not self.path:
            return False
        bin_dir = self.bin_dir()
        if self._is_windows:
            return (
                bin_dir.joinpath("activate").is_file()
                and bin_dir.joinpath("python.exe").is_file()
                and self.path.joinpath("Lib", "site-packages").is_dir()
            )
        return (
            bin_dir.joinpath("activate").is_file()
            and bin_dir.joinpath("python").is_file()
            and bool(
                next(
                    self.path.glob(os.path.sep.join(("lib", "python3*", "site-packages"))),  # type: ignore
                    False,
                )
            )
        )

    def get_env_vars(self, base_env: MutableMapping[str, str]) -> Dict[str, str]:
        path_delim = ";" if self._is_windows else ":"
        result = dict(
            base_env,
            VIRTUAL_ENV=str(self.path),
            PATH=f"{self.bin_dir()}{path_delim}{os.environ.get('PATH', '')}",
        )
        if "PYTHONHOME" in result:
            result.pop("PYTHONHOME")
        return result
