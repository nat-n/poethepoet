import shutil
from functools import cached_property
from pathlib import Path
from subprocess import PIPE, Popen


class GitRepo:
    def __init__(self, seed_path: Path):
        self._seed_path = seed_path

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

    def init(self):
        self._exec("init")

    def delete_git_dir(self):
        shutil.rmtree(self._seed_path.joinpath(".git"))

    def _resolve_path(self) -> Path | None:
        """
        Resolve the path of this git repo
        """
        proc, captured_stdout = self._exec(
            "rev-parse", "--show-superproject-working-tree", "--show-toplevel"
        )
        if proc.returncode == 0:
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
        proc, captured_stdout = self._exec(
            "rev-parse", "--show-superproject-working-tree", "--show-toplevel"
        )
        if proc.returncode == 0:
            return Path(captured_stdout.decode().strip().split("\n")[0])
        return None

    def _exec(self, *args: str) -> tuple[Popen, bytes]:
        proc = Popen(
            ["git", *args],
            cwd=self._seed_path,
            stdout=PIPE,
            stderr=PIPE,
        )
        captured_stdout, _ = proc.communicate()
        return proc, captured_stdout
