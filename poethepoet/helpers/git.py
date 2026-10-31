from __future__ import annotations

import shutil
from functools import cached_property
from pathlib import Path
from subprocess import PIPE, Popen
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..io import PoeIO


def git_unset_reason(git_repo: GitRepo, git_var: str) -> str:
    """
    Explain why the given git variable has no value. If git is missing then poe has
    already warned about that, so don't repeat it.
    """
    if git_repo.git_missing:
        return f"{git_var} has no value"
    return f"the project is not inside a git repository, so {git_var} has no value"


class GitRepo:
    def __init__(self, seed_path: Path, io: PoeIO | None = None):
        self._seed_path = seed_path
        self._io = io
        self._git_missing = False

    @property
    def seed_path(self) -> Path:
        return self._seed_path

    @cached_property
    def path(self) -> Path | None:
        # Cached even if None, so git isn't run again for each reference outside a repo
        return self._resolve_path()

    @cached_property
    def main_path(self) -> Path | None:
        return self._resolve_main_path()

    @property
    def git_missing(self) -> bool:
        """
        Whether the git executable couldn't be found, so no git repo can be found.
        """
        return self._git_missing

    def init(self):
        self._exec("init")

    def delete_git_dir(self):
        shutil.rmtree(self._seed_path.joinpath(".git"))

    def _resolve_path(self) -> Path | None:
        """
        Resolve the path of this git repo
        """
        returncode, captured_stdout = self._exec(
            "rev-parse", "--show-superproject-working-tree", "--show-toplevel"
        )
        if returncode == 0:
            captured_lines = (
                line.strip() for line in captured_stdout.decode().strip().split("\n")
            )
            longest_line = max((len(line), line) for line in captured_lines)[1]
            return Path(longest_line)
        return None

    def _resolve_main_path(self) -> Path | None:
        """
        Resolve the path of this git repo, unless this repo is a git submodule,
        then resolve the path of the main git repo.
        """
        returncode, captured_stdout = self._exec(
            "rev-parse", "--show-superproject-working-tree", "--show-toplevel"
        )
        if returncode == 0:
            return Path(captured_stdout.decode().strip().split("\n")[0])
        return None

    def _exec(self, *args: str) -> tuple[int, bytes]:
        try:
            proc = Popen(
                ["git", *args],
                cwd=self._seed_path,
                stdout=PIPE,
                stderr=PIPE,
            )
        except OSError:
            # The git executable isn't available, so no git repo can be found
            if not self._git_missing:
                self._git_missing = True
                if self._io:
                    self._io.print_warning(
                        "Poe could not find the git executable, so POE_GIT_DIR and "
                        "POE_GIT_ROOT have no value"
                    )
            return 1, b""
        captured_stdout, _ = proc.communicate()
        return proc.returncode, captured_stdout
