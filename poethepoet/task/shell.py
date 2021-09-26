import os
import shutil
import subprocess
from typing import Dict, MutableMapping, Sequence, Type, TYPE_CHECKING
from ..exceptions import PoeException
from .base import PoeTask

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext


class ShellTask(PoeTask):
    """
    A task consisting of a reference to a shell command
    """

    content: str

    __key__ = "shell"
    __options__: Dict[str, Type] = {}

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: MutableMapping[str, str],
    ) -> int:
        env, has_named_args = self._add_named_args_to_env(extra_args, env)

        if not has_named_args and any(arg.strip() for arg in extra_args):
            raise PoeException(f"Shell task {self.name!r} does not accept arguments")

        if self._is_windows:
            shell = self._find_posix_shell_on_windows()
        else:
            # Prefer to use configured shell, otherwise look for bash
            shell = [os.environ.get("SHELL", shutil.which("bash") or "/bin/bash")]

        self._print_action(self.content, context.dry)
        return context.get_executor(self.invocation, env, self.options).execute(
            shell, input=self.content.encode()
        )

    def _add_named_args_to_env(
        self, extra_args: Sequence[str], env: MutableMapping[str, str]
    ):
        named_args = self.parse_named_args(extra_args)
        if named_args is None:
            return env, False
        return dict(env, **named_args), bool(named_args)

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
