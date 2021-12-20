from shutil import which
import sys
from typing import (
    Any,
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

        interpreter = self.resolve_interpreter()
        if not interpreter:
            config_value = self._get_interpreter_config()
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

    def _get_interpreter_config(self) -> Tuple[str, ...]:
        result: Union[str, Tuple[str, ...]] = self.options.get(
            "interpreter", self._config.shell_interpreter
        )
        if isinstance(result, str):
            return (result,)
        return tuple(result)

    def resolve_interpreter(self) -> Optional[str]:
        for item in self._get_interpreter_config():
            return self._locate_interpreter(item)
        return None

    def _locate_interpreter(self, interpreter: str) -> Optional[str]:
        result = None

        if interpreter == "posix":
            # look for any known posix shell
            result = (
                self._locate_interpreter("sh")
                or self._locate_interpreter("bash")
                or self._locate_interpreter("zsh")
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
        valid_interpreters = config.KNOWN_SHELL_INTERPRETERS

        if isinstance(interpreter, str) and interpreter not in valid_interpreters:
            return (
                "Unsupported value for option `interpreter` for task "
                f"{task_name!r}. Expected one of {valid_interpreters}"
            )

        if isinstance(interpreter, list):
            if len(interpreter) == 0:
                return (
                    "Unsupported value for option `interpreter` for task "
                    f"{task_name!r}. Expected at least one item in list."
                )
            for item in interpreter:
                if item not in valid_interpreters:
                    return (
                        "Unsupported item {item!r} in option `interpreter` for task "
                        f"{task_name!r}. Expected one of {valid_interpreters}"
                    )

        return None
