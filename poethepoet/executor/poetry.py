import os
import shutil
from typing import Optional, Sequence
from .base import PoeExecutor


class PoetryExecutor(PoeExecutor):
    """
    A poe task executor implementation that executes inside a poetry managed dev
    environment
    """

    def execute(self, cmd: Sequence[str], input: Optional[bytes] = None,) -> int:
        """
        Execute the given cmd as a subprocess inside the poetry managed dev environment
        """
        if bool(os.environ.get("POETRY_ACTIVE")):
            # We're already inside a poetry shell
            return self._exec_via_subproc(cmd, input=input)
        else:
            # Execute the task via the `poetry run` CLI
            poetry_cmd = shutil.which("poetry") or "poetry"
            return self._exec_via_subproc((poetry_cmd, "run", *cmd), input=input)
