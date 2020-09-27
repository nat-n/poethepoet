from subprocess import Popen, PIPE
import os
from pathlib import Path
from shlex import quote
import shutil
import sys
from typing import Optional, Sequence
from .base import PoeExecutor


class PoetryExecutor(PoeExecutor):
    """
    A poe task executor implementation that executes inside a poetry managed dev
    environment
    """

    def execute(self, cmd: Sequence[str], input: Optional[bytes] = None) -> int:
        """
        Execute the given cmd as a subprocess inside the poetry managed dev environment
        """

        if bool(os.environ.get("POETRY_ACTIVE")) or self.context.poe_active == "poetry":
            # We're already inside a poetry shell or a recursive poe call so we can
            # execute the command unaltered
            return self._execute_cmd(cmd, input)

        if self.context.multistage:
            # This run involves multiple executions so it's worth trying to avoid
            # repetative (and expensive) calls to `poetry run` if we can
            poetry_env = self._get_poetry_virtualenv()
            if sys.prefix == poetry_env:
                # poetry environment is already activated
                return self._execute_cmd(cmd, input)

            # Find the virtualenv activate script and execute the cmd in a shell
            # with with the virtualenv
            # This doesn't work on windows (though maybe it could be made to).
            activate_script = self._get_activate_script(poetry_env)
            if activate_script:
                # Activate the virtualenv before running the task. This is much faster
                # than poetry run
                return self._execute_cmd(
                    " ".join(
                        (
                            "source",
                            quote(activate_script),
                            "&&",
                            *(quote(token) for token in cmd),
                        )
                    ),
                    input,
                    shell=True,
                )

        return self._execute_cmd((self._poetry_cmd(), "run", *cmd), input)

    def _execute_cmd(
        self, cmd: Sequence[str], input: Optional[bytes] = None, shell: bool = False
    ) -> int:
        return self._exec_via_subproc(
            cmd, input=input, env=dict(self.env, POE_ACTIVE="poetry"), shell=shell
        )

    def _get_activate_script(self, poetry_env: Optional[str] = None) -> Optional[str]:
        """
        Try locate the appropriate poetry virtualenv activate script
        This doesn't work on windows (though maybe it could be made to).
        """
        exec_cache = self.context.exec_cache
        result = exec_cache.get("poetry_activate_script")
        if "poetry_activate_script" in exec_cache:
            return result

        if os.name == "posix":
            shell_name = Path(os.environ.get("SHELL", "")).stem
            if shell_name:
                poetry_env = poetry_env or self._get_poetry_virtualenv()

                if "fish" == shell_name:
                    suffix = ".fish"
                elif "csh" == shell_name:
                    suffix = ".csh"
                elif "tcsh" == shell_name:
                    suffix = ".csh"
                else:
                    suffix = ""

                activate_path = (
                    Path(poetry_env).resolve().joinpath("bin", "activate" + suffix)
                )
                if activate_path.is_file():
                    result = str(activate_path)

        # result might be None but we still want to cache it to avoid trying again
        exec_cache["poetry_activate_script"] = result
        return result

    def _get_poetry_virtualenv(self):
        """
        Ask poetry where it put the virtualenv for this project.
        This is a relatively expensive operation so uses the context.exec_cache
        """
        if "poetry_virtualenv" not in self.context.exec_cache:
            self.context.exec_cache["poetry_virtualenv"] = (
                Popen((self._poetry_cmd(), "env", "info", "-p"), stdout=PIPE)
                .communicate()[0]
                .decode()
                .strip()
            )
        return self.context.exec_cache["poetry_virtualenv"]

    def _poetry_cmd(self):
        return shutil.which("poetry") or "poetry"
