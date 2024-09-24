from __future__ import annotations

from typing import Optional


# ruff: noqa: N818
class PoeException(RuntimeError):
    cause: str | None

    def __init__(self, msg, *args):
        self.msg = msg
        self.cause = args[0].args[0] if args else None
        self.args = (msg, *args)


class CyclicDependencyError(PoeException):
    pass


class ExpressionParseError(PoeException):
    pass


class ConfigValidationError(PoeException):
    context: str | None
    task_name: str | None
    index: int | None
    global_option: str | None
    filename: str | None

    def __init__(
        self,
        msg,
        *args,
        context: str | None = None,
        task_name: str | None = None,
        index: int | None = None,
        global_option: str | None = None,
        filename: str | None = None
    ):
        super().__init__(msg, *args)
        self.context = context
        self.task_name = task_name
        self.index = index
        self.global_option = global_option
        self.filename = filename


class ExecutionError(RuntimeError):
    cause: str | None

    def __init__(self, msg, *args):
        self.msg = msg
        self.cause = args[0].args[0] if args else None
        self.args = (msg, *args)


class PoePluginException(PoeException):
    pass
