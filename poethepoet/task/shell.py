import re
from collections.abc import Sequence
from os import environ
from pathlib import Path
from typing import TYPE_CHECKING

from ..exceptions import ConfigValidationError, PoeException
from ..executor.task_run import PoeTaskRun
from .base import PoeTask

if TYPE_CHECKING:
    from ..context import RunContext
    from ..env.manager import EnvVarsManager


class ShellTask(PoeTask):
    """
    A task consisting of a reference to a shell command
    """

    content: str

    __key__ = "shell"

    class TaskOptions(PoeTask.TaskOptions):
        interpreter: str | Sequence[str] | None = None

        def validate(self):
            super().validate()

            from ..config import KNOWN_SHELL_INTERPRETERS as VALID_INTERPRETERS

            if (
                isinstance(self.interpreter, str)
                and self.interpreter not in VALID_INTERPRETERS
            ):
                raise ConfigValidationError(
                    "Invalid value for option 'interpreter',\n"
                    f"Expected one of {VALID_INTERPRETERS}"
                )

            if isinstance(self.interpreter, list):
                if len(self.interpreter) == 0:
                    raise ConfigValidationError(
                        "Invalid value for option 'interpreter',\n"
                        "Expected at least one item in list."
                    )
                for item in self.interpreter:
                    if item not in VALID_INTERPRETERS:
                        raise ConfigValidationError(
                            f"Invalid item {item!r} in option 'interpreter',\n"
                            f"Expected one of {VALID_INTERPRETERS!r}"
                        )

    class TaskSpec(PoeTask.TaskSpec):
        content: str
        options: "ShellTask.TaskOptions"

    spec: TaskSpec

    async def _handle_run(
        self, context: "RunContext", env: "EnvVarsManager", task_state: PoeTaskRun
    ):
        named_arg_values, _ = self.get_parsed_arguments(env)
        env.update(named_arg_values)

        if not named_arg_values and any(arg.strip() for arg in self.invocation[1:]):
            raise PoeException(
                f"Shell task {self.spec.name!r} does not accept arguments"
            )

        interpreter_cmd = self.resolve_interpreter_cmd()
        if not interpreter_cmd:
            config_value = self._get_interpreter_config()
            message = (
                f"Couldn't locate interpreter executable for {config_value!r} to run "
                "shell task. "
            )
            if self._is_windows and set(config_value).issubset({"posix", "bash"}):
                message += "Installing Git Bash or using WSL should fix this."
            else:
                message += "Some dependencies may be missing from your system."
            raise PoeException(message)

        content = _unindent_code(self.spec.content).rstrip()

        self._print_action(content, context.dry)

        executor = self._get_executor(
            context, env, resolve_python=interpreter_cmd == "python"
        )
        process = await executor.execute(interpreter_cmd, input=content.encode())
        await task_state.add_process(process, finalize=True)

    def _get_interpreter_config(self) -> tuple[str, ...]:
        result: str | tuple[str, ...] = self.spec.options.get(
            "interpreter", self.ctx.config.shell_interpreter
        )
        if isinstance(result, str):
            return (result,)
        return tuple(result)

    def resolve_interpreter_cmd(self) -> list[str] | None:
        """
        Return a formatted command for the first specified interpreter that can be
        located.
        """
        for item in self._get_interpreter_config():
            executable = self._locate_interpreter(item)
            if executable is None:
                continue

            if item in ("pwsh", "powershell"):
                return [executable, "-NoLogo", "-Command", "-"]

            return [executable]

        return None

    def _locate_interpreter(self, interpreter: str) -> str | None:
        from shutil import which

        result = None
        prog_files = environ.get("PROGRAMFILES", "C:\\Program Files")

        # Try use $SHELL from the environment as a hint
        shell_var = environ.get("SHELL", "")
        if shell_var.endswith(f"/{interpreter}") and which(shell_var) == shell_var:
            result = shell_var

        elif interpreter == "posix":
            # look for any known posix shell
            result = (
                self._locate_interpreter("sh")
                or self._locate_interpreter("bash")
                or self._locate_interpreter("zsh")
            )

        elif interpreter == "sh":
            result = which("sh") or which("/bin/sh")

            # Specifically look for git sh on windows
            if result is None and self._is_windows:
                result = which(f"{prog_files}\\Git\\bin\\sh.exe")

                if result is None and (git_path_str := which("git")) is not None:
                    # Check if sh.exe can be found relative to the git executable
                    # in case git is installed at a non-standard location.
                    git_path = Path(git_path_str)
                    if (sh_path := git_path.parent.parent / "bin" / "sh.exe").exists():
                        result = str(sh_path)
        elif interpreter == "bash":
            if self._is_windows:
                # Specifically look for git bash on windows as the preferred option
                # Don't trust bash from the path because it might be a useless decoy
                result = (
                    which(f"{prog_files}\\Git\\bin\\bash.exe")
                    or which("/bin/bash")
                    or which("bash")
                )
            else:
                result = which("bash") or which("/bin/bash")

        elif interpreter == "zsh":
            result = which("zsh") or which("/bin/zsh")

        elif interpreter == "fish":
            result = which("fish") or which("/bin/fish")

        elif interpreter in ("pwsh", "powershell"):
            # Look for the pwsh executable and verify the version matches
            result = (
                which("pwsh")
                or which(f"{prog_files}\\PowerShell\\7\\pwsh.exe")
                or which(f"{prog_files}\\PowerShell\\6\\pwsh.exe")
            )

            if result is None and interpreter == "powershell" and self._is_windows:
                # Look for older versions of powershell
                result = which("powershell") or which(
                    environ.get("WINDIR", "C:\\Windows")
                    + "\\System32\\WindowsPowerShell\\v1.0\\powershell.EXE"
                )

        elif interpreter == "python":
            # Exactly which python executable to use is usually resolved by the executor
            result = "python"

        return result


def _unindent_code(python_code: str):
    """
    Unindent all lines by the indent level of the first line.
    This is rather naive, but should usually work as one would naively expect for a
    multiline script in a multiline string value in toml.

    It will not always work correctly if the multiline string itself contains a triple
    quoted multiline python string or similar. Let's say that's OK for now.
    """

    if not python_code.startswith(" "):
        return python_code

    indent = 0
    while python_code[indent] == " ":
        indent += 1

    prefix = " " * indent
    return "\n".join(
        line.removeprefix(prefix) for line in re.split(r"(?:\r\n|\r|\n)", python_code)
    )
