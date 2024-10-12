# ruff: noqa: E501
import shutil
from pathlib import Path
from typing import Union


def rm(
    *patterns: str,
    cwd: str = ".",
    verbosity: Union[int, str] = 0,
    dry_run: bool = False,
):
    """
    This function is intended for use in a script task to delete files and directories
    matching the given patterns, as a platform agnostic alternative to the `rm -rf`

    Example usage:

    .. code-block:: toml

        [tool.poe.tasks.clean]
        script = "poethepoet.scripts:rm('.mypy_cache', '.pytest_cache', './**/__pycache__')"
    """
    verbosity = int(verbosity)

    for pattern in patterns:
        matches = list(Path(cwd).glob(pattern))
        if verbosity > 0 and not matches:
            print(f"No files or directories to delete matching {pattern!r}")
        elif verbosity >= 0 and len(matches) > 1:
            print(f"Deleting paths matching {pattern!r}")

        for match in matches:
            _delete_path(match, verbosity, dry_run)


def _delete_path(path: Path, verbosity: int, dry_run: bool):
    if path.is_dir():
        if verbosity > 0:
            print(f"Deleting directory '{path}'")
        if not dry_run:
            shutil.rmtree(path)
    else:
        if verbosity > 0:
            print(f"Deleting file '{path}'")
        if not dry_run:
            path.unlink()
