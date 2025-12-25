from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from ..options.annotations import Metadata
from .base import PoeExecutor

if TYPE_CHECKING:
    from asyncio.subprocess import Process
    from collections.abc import Sequence

    from ..context import ContextProtocol


class UvExecutor(PoeExecutor):
    """
    A poe task executor implementation that executes inside a uv managed dev
    environment
    """

    __key__ = "uv"

    class ExecutorOptions(PoeExecutor.ExecutorOptions):
        extra: str | list[str] | None = None
        group: str | list[str] | None = None
        no_group: Annotated[
            str | list[str] | None, Metadata(config_name="no-group")
        ] = None
        with_: Annotated[str | list[str] | None, Metadata(config_name="with")] = None
        isolated: bool = False
        no_sync: Annotated[bool, Metadata(config_name="no-sync")] = False
        locked: bool = False
        frozen: bool = False
        no_project: Annotated[bool, Metadata(config_name="no-project")] = False
        python: str | None = None

    __uv_cli_options = ("extra", "group", "no-group", "with", "python")
    __uv_cli_flags = ("isolated", "no-sync", "locked", "frozen", "no-project")

    @classmethod
    def works_with_context(cls, context: ContextProtocol) -> bool:
        if not context.config.is_uv_project:
            return False
        return bool(cls._uv_cmd_from_path())

    async def execute(
        self, cmd: Sequence[str], input: bytes | None = None, use_exec: bool = False
    ) -> Process:
        """
        Execute the given cmd as a subprocess via `uv run`.
        """

        uv_run_options = []

        if self._io.verbosity > 0:
            uv_run_options.append("-v")
        elif self._io.verbosity < 0:
            uv_run_options.append("-q")

        if self.working_dir:
            # Explicitly set the working directory and project directory for uv
            uv_run_options.append(f"--directory={self.working_dir}")
            uv_run_options.append(f"--project={self.context.config.project_dir}")

        uv_run_options.extend(
            f"--{key}={item}"
            for key in self.__uv_cli_options
            if (value := self.options.get(key))
            for item in ((value,) if isinstance(value, str) else value)
        )
        uv_run_options.extend(
            f"--{key}" for key in self.__uv_cli_flags if self.options.get(key)
        )

        # Run this task with `uv run`
        return await self._execute_cmd(
            (self._uv_cmd(), "run", *uv_run_options, *cmd),
            input=input,
            use_exec=use_exec,
        )

    @classmethod
    def _uv_cmd(cls):
        if from_path := cls._uv_cmd_from_path():
            return from_path

        return "uv"

    @classmethod
    def _uv_cmd_from_path(cls):
        import shutil

        return shutil.which("uv")
