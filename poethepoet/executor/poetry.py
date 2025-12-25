from __future__ import annotations

import asyncio
from os import environ
from pathlib import Path
from typing import TYPE_CHECKING

from ..exceptions import ExecutionError
from .base import PoeExecutor

if TYPE_CHECKING:
    from asyncio.subprocess import Process
    from collections.abc import Sequence

    from ..context import ContextProtocol


class PoetryExecutor(PoeExecutor):
    """
    A poe task executor implementation that executes inside a poetry managed dev
    environment
    """

    __key__ = "poetry"

    @classmethod
    def works_with_context(cls, context: ContextProtocol) -> bool:
        if not context.config.is_poetry_project:
            return False
        return bool(cls._poetry_cmd_from_path())

    async def execute(
        self, cmd: Sequence[str], input: bytes | None = None, use_exec: bool = False
    ) -> Process:
        """
        Execute the given cmd as a subprocess inside the poetry managed dev environment
        """

        poetry_env = await self._get_poetry_virtualenv()

        if poetry_env:
            from ..virtualenv import Virtualenv

            # Execute the task in the virtualenv from poetry, this is much faster than
            # invoking `poetry run` each time.
            venv = Virtualenv(Path(poetry_env))
            return await self._execute_cmd(
                (venv.resolve_executable(cmd[0]), *cmd[1:]),
                input=input,
                env=venv.get_env_vars(self.env.to_dict()),
                use_exec=use_exec,
            )

        if self._virtualenv_creation_disabled():
            # There's no poetry env, and there isn't going to be
            cmd = (*self._resolve_executable(cmd[0]), *cmd[1:])
            return await self._execute_cmd(cmd, input=input, use_exec=use_exec)

        # Run this task with `poetry run`
        return await self._execute_cmd(
            (self._poetry_cmd(), "--no-plugins", "run", *cmd),
            input=input,
            use_exec=use_exec,
        )

    async def _handle_file_not_found(
        self, cmd: Sequence[str], error: FileNotFoundError
    ):
        poetry_env = await self._get_poetry_virtualenv()
        error_context = f" using virtualenv {poetry_env!r}" if poetry_env else ""
        raise ExecutionError(
            f"executable {cmd[0]!r} could not be found{error_context}"
        ) from error

    async def _get_poetry_virtualenv(self):
        """
        Ask poetry where it put the virtualenv for this project.
        Invoking poetry is relatively expensive so cache the result
        """

        # TODO: see if there's a more efficient way to do this that doesn't involve
        #       invoking the poetry cli or relying on undocumented APIs

        exec_cache = self.context.exec_cache

        if "poetry_virtualenv" not in exec_cache:
            from subprocess import PIPE

            # Need to make sure poetry isn't influenced by whatever virtualenv is
            # currently active
            clean_env = dict(environ)
            clean_env.pop("VIRTUAL_ENV", None)
            clean_env["PYTHONIOENCODING"] = "utf-8"

            proc = await asyncio.create_subprocess_exec(
                self._poetry_cmd(),
                "--no-plugins",
                "env",
                "info",
                "-p",
                stdout=PIPE,
                cwd=self.context.config.project_dir,
                env=clean_env,
            )
            outputs = await proc.communicate()
            exec_cache["poetry_virtualenv"] = outputs[0].decode().strip()

        return exec_cache.get("poetry_virtualenv")

    @classmethod
    def _poetry_cmd(cls):
        if from_path := cls._poetry_cmd_from_path():
            return from_path

        return "poetry"

    @classmethod
    def _poetry_cmd_from_path(cls):
        import shutil

        return shutil.which("poetry")

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
