class PoeException(RuntimeError):
    def __init__(self, msg, *args):
        self.msg = msg
        self.cause = args[0].args[0] if args else None
        self.args = (msg, *args)


class CyclicDependencyError(PoeException):
    pass


class ExecutionError(RuntimeError):
    def __init__(self, msg, *args):
        self.msg = msg
        self.cause = args[0].args[0] if args else None
        self.args = (msg, *args)
