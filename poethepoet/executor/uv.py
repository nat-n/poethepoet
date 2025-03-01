from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .base import PoeExecutor

if TYPE_CHECKING:
    from ..context import RunContext


class UvExecutor(PoeExecutor):
    """
    A poe task executor implementation that executes inside a uv managed dev
    environment
    """

    __key__ = "uv"
    __options__: dict[str, type] = {}

    @classmethod
    def works_with_context(cls, context: "RunContext") -> bool:
        if not context.config.is_uv_project:
            return False
        return bool(cls._uv_cmd_from_path())

    def execute(
        self, cmd: Sequence[str], input: Optional[bytes] = None, use_exec: bool = False
    ) -> int:
        """
        Execute the given cmd as a subprocess inside the uv managed dev environment.

        We simply use `uv run`, which handles the virtualenv and other setup for us.
        """

        uv_run_options = []
        if self.context.ui.verbosity > 0:
            uv_run_options.append("-v")
        elif self.context.ui.verbosity < 0:
            uv_run_options.append("-q")

        # Run this task with `uv run`
        return self._execute_cmd(
            (self._uv_cmd(), "run", *uv_run_options, *cmd),
            input=input,
            use_exec=use_exec,
        )

    @classmethod
    def _uv_cmd(cls):
        from_path = cls._uv_cmd_from_path()
        if from_path:
            return str(Path(from_path).resolve())

        return "uv"

    @classmethod
    def _uv_cmd_from_path(cls):
        import shutil

        return shutil.which("uv")
