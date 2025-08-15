from asyncio.subprocess import Process


class PoeExecutionResult:
    """
    A class to represent the result of a Poe task execution.
    It can encapsulate multiple subprocesses and their results.
    """

    def __init__(self, *processes: Process):
        self.processes = processes

    @property
    def non_zero_exit_code(self) -> int:
        return self.returncode > 0

    @property
    def returncode(self) -> int:
        # FIXME: check if all processes have completed??
        return sum(
            proc.returncode for proc in self.processes if proc.returncode is not None
        )
