from typing import Optional


# ruff: noqa: N818
class PoeException(RuntimeError):
    cause: Optional[str]

    def __init__(self, msg, *args):
        self.msg = msg
        self.cause = args[0].args[0] if args else None
        self.args = (msg, *args)


class CyclicDependencyError(PoeException):
    pass


class ExpressionParseError(PoeException):
    pass


class ConfigValidationError(PoeException):
    context: Optional[str]
    task_name: Optional[str]
    index: Optional[int]
    global_option: Optional[str]
    filename: Optional[str]

    def __init__(
        self,
        msg,
        *args,
        context: Optional[str] = None,
        task_name: Optional[str] = None,
        index: Optional[int] = None,
        global_option: Optional[str] = None,
        filename: Optional[str] = None
    ):
        super().__init__(msg, *args)
        self.context = context
        self.task_name = task_name
        self.index = index
        self.global_option = global_option
        self.filename = filename


class ExecutionError(RuntimeError):
    cause: Optional[str]

    def __init__(self, msg, *args):
        self.msg = msg
        self.cause = args[0].args[0] if args else None
        self.args = (msg, *args)


class PoePluginException(PoeException):
    pass
