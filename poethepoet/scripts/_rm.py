# ruff: noqa: E501
import shutil
from pathlib import Path


def rm(
    *patterns: str,
    cwd: str = ".",
    verbosity: int | str = 0,
    dry_run: bool = False,
):
    """
    This function is intended for use in a script task to delete files and directories
    matching any of the given patterns, as a platform agnostic alternative to
    ``rm -rf [patterns]``

    Example usage:

    .. code-block:: toml

        [tool.poe.tasks.clean]
        script = "poethepoet.scripts:rm('.mypy_cache', '.pytest_cache', './**/__pycache__')"

    :param *patterns:
        One or more paths to delete.
        `Glob patterns <https://docs.python.org/3/library/glob.html>`_ are supported.
    :param cwd:
        The directory relative to which patterns are evaluated. Defaults to ``.``.
    :param verbosity:
        An integer for setting the function's verbosity. This can be set to
        ``environ.get('POE_VERBOSITY')`` to match the verbosity of the poe invocation.
    :param dry_run:
        If true then nothing will be deleted, but output to stdout will be unaffected.
        This can be set to ``_dry_run`` to make poe delegate dry_run control to the
        function.
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
