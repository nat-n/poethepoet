from shutil import which
import sys
from typing import (
    Any,
    cast,
    Dict,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)
from ..exceptions import PoeException
from .base import PoeTask

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext

KNOWN_INTERPRETERS = ("posix", "sh", "bash", "zsh", "fish", "pwsh", "python")
DEFAULT_INTERPRETER = "posix"


class ShellTask(PoeTask):
    """
    A task consisting of a reference to a shell command
    """

    content: str

    __key__ = "shell"
    __options__: Dict[str, Union[Type, Tuple[Type, ...]]] = {"interpreter": (str, list)}

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: Mapping[str, str],
    ) -> int:
        env, has_named_args = self.add_named_args_to_env(env)

        if not has_named_args and any(arg.strip() for arg in extra_args):
            raise PoeException(f"Shell task {self.name!r} does not accept arguments")

        interpreter = self.locate_interpreter()
        if not interpreter:
            config_value = self.options.get("interpreter", "bash")
            message = f"Couldn't locate interpreter executable for {config_value!r} to run shell task. "
            if self._is_windows and config_value in ("posix", "bash"):
                message += "Installing Git Bash or using WSL should fix this."
            else:
                message += "Some dependencies may be missing from your system."
            raise PoeException(message)

        self._print_action(self.content, context.dry)
        return context.get_executor(self.invocation, env, self.options).execute(
            [interpreter], input=self.content.encode()
        )

    def locate_interpreter(self, interpreter: Optional[str] = None) -> Optional[str]:
        result = None
        if interpreter is None:
            interpreter = self.options.get("interpreter", DEFAULT_INTERPRETER)

        if isinstance(interpreter, list):
            for item in cast(list, interpreter):
                result = self.locate_interpreter(item)
                if result is not None:
                    break

        if interpreter == "posix":
            # look for any known posix shell
            result = (
                self.locate_interpreter("sh")
                or self.locate_interpreter("bash")
                or self.locate_interpreter("zsh")
            )

        elif interpreter == "sh":
            result = which("sh") or which("/bin/sh")

        elif interpreter == "bash":
            result = which("bash") or which("/bin/bash")

            # Specifically look for git bash on windows
            if result is None and self._is_windows:
                result = which("C:\\Program Files\\Git\\bin\\bash.exe")

        elif interpreter == "zsh":
            result = which("zsh") or which("/bin/zsh")

        elif interpreter == "fish":
            result = which("fish") or which("/bin/fish")

        elif interpreter == "pwsh":
            result = which("pwsh") or which("powershell")

            # Specifically look in a known location on windows
            if result is None and self._is_windows:
                result = which(
                    "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.EXE"
                )

        elif interpreter == "python":
            result = which("python") or which("python3") or sys.executable

        return result

    @classmethod
    def _validate_task_def(
        cls, task_name: str, task_def: Dict[str, Any], config: "PoeConfig"
    ) -> Optional[str]:
        interpreter = task_def.get("interpreter")
        if isinstance(interpreter, str) and interpreter not in KNOWN_INTERPRETERS:
            return (
                "Unsupported value for option `interpreter` for task "
                f"{task_name!r}. Expected one of {KNOWN_INTERPRETERS}"
            )

        if isinstance(interpreter, list):
            if len(interpreter) == 0:
                return (
                    "Unsupported value for option `interpreter` for task "
                    f"{task_name!r}. Expected at least one item in list."
                )
            for item in interpreter:
                if item not in KNOWN_INTERPRETERS:
                    return (
                        "Unsupported item {item!r} in option `interpreter` for task "
                        f"{task_name!r}. Expected one of {KNOWN_INTERPRETERS}"
                    )

        return None
