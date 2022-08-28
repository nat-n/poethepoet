from subprocess import Popen, PIPE
from os import environ
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

    def execute(
        self, cmd: Sequence[str], input: Optional[bytes] = None, use_exec: bool = False
    ) -> int:
        """
        Execute the given cmd as a subprocess inside the poetry managed dev environment
        """

        poetry_env = self._get_poetry_virtualenv()
        project_dir = self.context.config.project_dir

        if sys.prefix == poetry_env or (
            (
                bool(environ.get("POETRY_ACTIVE"))
                or self.context.poe_active == PoetryExecutor.__key__
            )
            and project_dir == environ.get("POE_ROOT", project_dir)
        ):
            # The target venv is already active so we can execute the command unaltered
            return self._execute_cmd(cmd, input=input, use_exec=use_exec)

        if poetry_env:
            # Execute the task in the virtualenv from poetry
            venv = Virtualenv(Path(poetry_env))
            return self._execute_cmd(
                (venv.resolve_executable(cmd[0]), *cmd[1:]),
                input=input,
                env=venv.get_env_vars(self.env.to_dict()),
                use_exec=use_exec,
            )

        if self._virtualenv_creation_disabled():
            # There's no poetry env, and there isn't going to be
            return self._execute_cmd(cmd, input=input, use_exec=use_exec)

        # Run this task with `poetry run`
        return self._execute_cmd(
            (self._poetry_cmd(), "run", *cmd),
            input=input,
            use_exec=use_exec,
        )

    def _get_poetry_virtualenv(self, force: bool = True):
        """
        Ask poetry where it put the virtualenv for this project.
        Invoking poetry is relatively expensive so cache the result
        """

        # TODO: see if there's a more efficient way to do this that doesn't involve
        #       invoking the poetry cli or relying on undocumented APIs

        exec_cache = self.context.exec_cache

        if force and "poetry_virtualenv" not in exec_cache:
            # Need to make sure poetry isn't influenced by whatever virtualenv is
            # currently active
            clean_env = dict(environ)
            clean_env.pop("VIRTUAL_ENV", None)

            exec_cache["poetry_virtualenv"] = (
                Popen(
                    (self._poetry_cmd(), "env", "info", "-p"),
                    stdout=PIPE,
                    cwd=self.context.config.project_dir,
                    env=clean_env,
                )
                .communicate()[0]
                .decode()
                .strip()
            )

        return exec_cache.get("poetry_virtualenv")

    def _poetry_cmd(self):
        return shutil.which("poetry") or "poetry"

    def _virtualenv_creation_disabled(self):
        exec_cache = self.context.exec_cache

        while "poetry_virtualenvs_create_disabled" not in exec_cache:
            # Check env override
            env_override = environ.get("POETRY_VIRTUALENVS_CREATE")
            if env_override is not None:
                exec_cache["poetry_virtualenvs_create_disabled"] = (
                    env_override == "false"
                )
                break

            # A complete implementation would also check for a local poetry config file
            # and a global poetry config file (location for this is platform dependent)
            # in that order but just checking the env will do for now.
            break

        return exec_cache.get("poetry_virtualenvs_create_disabled", False)
