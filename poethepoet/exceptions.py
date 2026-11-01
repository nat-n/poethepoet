# ruff: noqa: N818


class PoeException(RuntimeError):
    cause: str | None

    def __init__(self, msg, *args):
        super().__init__(msg, *args)
        self.msg = msg

        if args:
            cause = args[0]
            position_clause = (
                f", near {cause.location}."
                if getattr(cause, "has_position", False)
                else "."
            )
            self.cause = cause.args[0] + position_clause
        else:
            self.cause = None


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
        filename: str | None = None,
    ):
        super().__init__(msg, *args)
        self.context = context
        self.task_name = task_name
        self.index = index
        self.global_option = global_option
        self.filename = filename


class ExecutionError(RuntimeError):
    cause: str | None
    causes: tuple[str, ...]

    def __init__(self, msg, *args):
        self.msg = msg
        self.causes = self._collect_causes(args[0]) if args else ()
        self.cause = self.causes[0] if self.causes else None
        self.args = (msg, *args)

    @staticmethod
    def _collect_causes(cause: BaseException) -> tuple[str, ...]:
        """
        Flatten an explicit cause into messages ordered from outermost to innermost.
        """
        if isinstance(cause, ExecutionError):
            return (cause.msg, *cause.causes)
        if isinstance(cause, PoeException):
            return (cause.msg, *((cause.cause,) if cause.cause else ()))
        return (cause.args[0],)


class PoePluginException(PoeException):
    pass
