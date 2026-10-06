# ruff: noqa: E501
import shutil
import sys
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
    failed = False

    for pattern in patterns:
        matches = _glob(pattern, cwd)
        if verbosity > 0 and not matches:
            print(f"No files or directories to delete matching {pattern!r}")
        elif verbosity >= 0 and len(matches) > 1:
            print(f"Deleting paths matching {pattern!r}")

        for match in matches:
            if not _delete_path(match, verbosity, dry_run):
                failed = True

    if failed:
        raise SystemExit(1)


def _glob(pattern: str, cwd: str) -> list[Path]:
    """
    Return the paths matching the given pattern, which may be relative to cwd or
    absolute.
    """
    if not pattern:
        return []

    base_dir = Path(cwd)
    relative_pattern = pattern
    if (pattern_path := Path(pattern)).is_absolute():
        # pathlib only supports globbing with relative patterns
        base_dir = Path(pattern_path.anchor)
        relative_pattern = str(pattern_path.relative_to(base_dir))
        if relative_pattern == ".":
            # Never delete a filesystem root
            return []

    try:
        return list(base_dir.glob(relative_pattern))
    except (ValueError, NotImplementedError) as error:
        message = str(error).removeprefix("Invalid pattern: ")
        raise SystemExit(f"Error: Invalid pattern {pattern!r}: {message}")


def _delete_path(path: Path, verbosity: int, dry_run: bool) -> bool:
    """
    Delete the given path, returning False if this failed.
    """
    if path.is_symlink():
        # Delete the link itself, rather than its target
        is_dir = False
    elif path.exists():
        is_dir = path.is_dir()
    else:
        # Already deleted, e.g. as the descendant of a previous match
        return True

    if verbosity > 0:
        print(f"Deleting {'directory' if is_dir else 'file'} '{path}'")
    if dry_run:
        return True

    try:
        if is_dir:
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    except OSError as error:
        print(
            f"Error: Failed to delete '{path}': {error.strerror or error}",
            file=sys.stderr,
        )
        return False
    return True
