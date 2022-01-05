from subprocess import Popen, PIPE
import os
from pathlib import Path
import shutil
import sys
from typing import Dict, Optional, Sequence, Type
from ..virtualenv import Virtualenv
from .base import PoeExecutor


class PoetryExecutor(PoeExecutor):
    """
    A poe task executor implementation that executes inside a poetry managed dev
    environment
    """

    __key__ = "poetry"
    __options__: Dict[str, Type] = {}

    def execute(self, cmd: Sequence[str], input: Optional[bytes] = None) -> int:
        """
        Execute the given cmd as a subprocess inside the poetry managed dev environment
        """

        # If this run involves multiple executions then it's worth trying to
        # avoid repetative (and expensive) calls to `poetry run` if we can
        poetry_env = self._get_poetry_virtualenv(force=self.context.multistage)

        if (
            bool(os.environ.get("POETRY_ACTIVE"))
            or self.context.poe_active == PoetryExecutor.__key__
            or sys.prefix == poetry_env
        ):
            # The target venv is already active so we can execute the command unaltered
            return self._execute_cmd(cmd, input)

        if poetry_env:
            # Execute the task in the virtualenv from poetry
            return self._execute_cmd(cmd, input, venv=Virtualenv(Path(poetry_env)))

        # Run this task with `poetry run`
        return self._execute_cmd((self._poetry_cmd(), "run", *cmd), input)

    def _execute_cmd(
        self,
        cmd: Sequence[str],
        input: Optional[bytes] = None,
        shell: bool = False,
        *,
        venv: Optional[Virtualenv] = None,
    ) -> int:
        if venv:
            return self._exec_via_subproc(
                (venv.resolve_executable(cmd[0]), *cmd[1:]),
                input=input,
                env=dict(
                    venv.get_env_vars(self.env), POE_ACTIVE=PoetryExecutor.__key__
                ),
            )

        return self._exec_via_subproc(
            cmd,
            input=input,
            env=dict(self.env, POE_ACTIVE=PoetryExecutor.__key__),
            shell=shell,
        )

    def _get_poetry_virtualenv(self, force: bool = True):
        """
        Ask poetry where it put the virtualenv for this project.
        This is a relatively expensive operation so uses the context.exec_cache
        """
        if force and "poetry_virtualenv" not in self.context.exec_cache:
            self.context.exec_cache["poetry_virtualenv"] = (
                Popen((self._poetry_cmd(), "env", "info", "-p"), stdout=PIPE)
                .communicate()[0]
                .decode()
                .strip()
            )
        return self.context.exec_cache.get("poetry_virtualenv")

    def _poetry_cmd(self):
        return shutil.which("poetry") or "poetry"
