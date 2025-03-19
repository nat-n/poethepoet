from __future__ import annotations

from typing import TYPE_CHECKING

from .base import PoeExecutor

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..context import ContextProtocol


class UvExecutor(PoeExecutor):
    """
    A poe task executor implementation that executes inside a uv managed dev
    environment
    """

    __key__ = "uv"
    __options__: dict[str, type] = {}

    @classmethod
    def works_with_context(cls, context: ContextProtocol) -> bool:
        if not context.config.is_uv_project:
            return False
        return bool(cls._uv_cmd_from_path())

    def execute(
        self, cmd: Sequence[str], input: bytes | None = None, use_exec: bool = False
    ) -> int:
        """
        Execute the given cmd as a subprocess inside the uv managed dev environment.

        We simply use `uv run`, which handles the virtualenv and other setup for us.
        """

        uv_run_options = []
        if self.context.ui and self.context.ui.verbosity > 0:
            uv_run_options.append("-v")
        elif self.context.ui and self.context.ui.verbosity < 0:
            uv_run_options.append("-q")

        if self.working_dir:
            # Explicitly set the working directory and project directory for uv
            uv_run_options.append(f"--directory={self.working_dir}")
            uv_run_options.append(f"--project={self.context.config.project_dir}")

        # Run this task with `uv run`
        return self._execute_cmd(
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
