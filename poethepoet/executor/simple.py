from typing import Dict, Optional, Sequence, Type
from .base import PoeExecutor


class SimpleExecutor(PoeExecutor):
    """
    A poe executor implementation that executes tasks without doing any special setup.
    """

    __key__ = "simple"
    __options__: Dict[str, Type] = {}

    def execute(self, cmd: Sequence[str], input: Optional[bytes] = None) -> int:
        """
        Execute the given cmd as a subprocess inside the poetry managed dev environment
        """
        return self._exec_via_subproc(
            cmd, input=input, env=dict(self.env, POE_ACTIVE=SimpleExecutor.__key__)
        )
