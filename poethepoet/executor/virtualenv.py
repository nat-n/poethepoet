from __future__ import annotations

from typing import TYPE_CHECKING

from ..exceptions import ExecutionError
from .base import PoeExecutor

if TYPE_CHECKING:
    from asyncio.subprocess import Process
    from collections.abc import Sequence

    from ..context import ContextProtocol
    from ..virtualenv import Virtualenv


class VirtualenvExecutor(PoeExecutor):
    """
    A poe task executor implementation that executes inside an arbitrary virtualenv
    """

    __key__ = "virtualenv"

    class ExecutorOptions(PoeExecutor.ExecutorOptions):
        location: str | None = None

    @classmethod
    def works_with_context(cls, context: ContextProtocol) -> bool:
        from ..virtualenv import Virtualenv

        return Virtualenv.detect(context.config.project_dir)

    async def execute(
        self, cmd: Sequence[str], input: bytes | None = None, use_exec: bool = False
    ) -> Process:
        """
        Execute the given cmd as a subprocess inside the configured virtualenv
        """
        venv = self._resolve_virtualenv()

        return await self._execute_cmd(
            (venv.resolve_executable(cmd[0]), *cmd[1:]),
            input=input,
            env=venv.get_env_vars(self.env.to_dict()),
            use_exec=use_exec,
        )

    async def _handle_file_not_found(
        self, cmd: Sequence[str], error: FileNotFoundError
    ):
        venv = self._resolve_virtualenv()
        error_context = f" using virtualenv {str(venv.path)!r}" if venv else ""
        raise ExecutionError(
            f"executable {cmd[0]!r} could not be found{error_context}"
        ) from error

    def _resolve_virtualenv(self) -> Virtualenv:
        from ..virtualenv import Virtualenv

        project_dir = self.context.config.project_dir

        if location := self.options.get("location"):
            venv_location = self.context.config.resolve_git_path(location)
            venv = Virtualenv(project_dir.joinpath(venv_location))
            if venv.valid():
                return venv

            raise ExecutionError(
                f"Could not find valid virtualenv at configured location: {venv.path}"
            )

        venv = Virtualenv(project_dir.joinpath("venv"))
        if venv.valid():
            return venv

        hidden_venv = Virtualenv(project_dir.joinpath(".venv"))
        if hidden_venv.valid():
            return hidden_venv

        raise ExecutionError(
            f"Could not find valid virtualenv at either of: {venv.path} or "
            f"{hidden_venv.path}.\n"
            "You can configure another location as tool.poe.executor.location"
        )
