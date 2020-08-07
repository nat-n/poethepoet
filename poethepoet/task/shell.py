import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Dict, Iterable, MutableMapping, Type, TYPE_CHECKING
from ..exceptions import PoeException
from .base import PoeTask

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..executor import PoeExecutor

_GLOBCHARS_PATTERN = re.compile(r".*[\*\?\[]")


class ShellTask(PoeTask):
    """
    A task consisting of a reference to a shell command
    """

    content: str

    __key__ = "shell"
    __options__: Dict[str, Type] = {}

    def _handle_run(
        self,
        executor: "PoeExecutor",
        extra_args: Iterable[str],
        project_dir: Path,
        env: MutableMapping[str, str],
        dry: bool = False,
    ) -> int:
        if any(arg.strip() for arg in extra_args):
            raise PoeException(f"Shell task {self.name!r} does not accept arguments")

        if self._is_windows:
            shell = self._find_posix_shell_on_windows()
        else:
            # Prefer to use configured shell, otherwise look for bash
            shell = [os.environ.get("SHELL", shutil.which("bash") or "/bin/bash")]

        self._print_action(self.content, dry)
        return executor.execute(shell, input=self.content.encode())

    @staticmethod
    def _find_posix_shell_on_windows():
        # Try locate a shell from the environment
        shell_from_env = shutil.which(os.environ.get("SHELL", "bash"))
        if shell_from_env:
            return [shell_from_env]

        # Try locate a bash from the environment
        bash_from_env = shutil.which("bash")
        if bash_from_env:
            return [bash_from_env]

        # Or check specifically for git bash
        bash_from_git = shutil.which("C:\\Program Files\\Git\\bin\\bash.exe")
        if bash_from_git:
            return [bash_from_git]

        # or use bash from wsl if it's available
        wsl = shutil.which("wsl")
        if wsl and subprocess.run(["wsl", "bash"], capture_output=True).returncode > 0:
            return [wsl, "bash"]

        # Fail: if there is a bash out there, we don't know how to get to it
        # > We don't know how to access wsl bash from python installed from python.org
        raise PoeException(
            "Couldn't locate bash executable to run shell task. Installing WSL should "
            "fix this."
        )
