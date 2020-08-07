from subprocess import Popen, PIPE
import sys
from typing import Any, MutableMapping, Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class PoeExecutor:
    """
    A base class for poe task executors
    """

    working_dir: Optional["Path"]

    # TODO: maybe recieve a reference to the PoeConfig
    #   Also maybe invert the control so the executor is given a task to run

    def __init__(
        self,
        env: MutableMapping[str, str],
        working_dir: Optional["Path"] = None,
        dry: bool = False,
    ):
        self.working_dir = working_dir
        self.env = env
        self.dry = dry

    def execute(self, cmd: Sequence[str], input: Optional[bytes] = None,) -> int:
        raise NotImplementedError

    def _exec_via_subproc(
        self,
        cmd: Sequence[str],
        *,
        env: Optional[MutableMapping[str, str]] = None,
        input: Optional[bytes] = None,
    ) -> int:
        if self.dry:
            return 0
        popen_kwargs: MutableMapping[str, Any] = {}
        popen_kwargs["env"] = self.env if env is None else env
        if input is not None:
            popen_kwargs["stdin"] = PIPE
        if self.working_dir is not None:
            popen_kwargs["cwd"] = self.working_dir

        # TODO: exclude the subprocess from coverage more gracefully
        _stop_coverage()

        proc = Popen(cmd, **popen_kwargs)
        proc.communicate(input)

        return proc.returncode


def _stop_coverage():
    """
    Running coverage around subprocesses seems to be problematic, esp. on windows.
    There's probably a more elegant solution that this.
    """
    if "coverage" in sys.modules:
        # If Coverage is running then it ends here
        from coverage import Coverage

        cov = Coverage.current()
        if cov:
            cov.stop()
            cov.save()
