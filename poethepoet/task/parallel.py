import sys
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypeVar, Union

from ..exceptions import ConfigValidationError, ExecutionError, PoeException
from ..executor.task_run import PoeTaskRun, PoeTaskRunError
from ..helpers.eventloop import DynamicTaskSet
from .base import PoeTask, TaskContext

if TYPE_CHECKING:
    from asyncio.subprocess import Process
    from collections.abc import Sequence

    from ..config import ConfigPartition, PoeConfig
    from ..context import RunContext
    from ..env.manager import EnvVarsManager
    from .base import TaskSpecFactory

T = TypeVar("T")


class ColorCycle:
    def __init__(self):
        self.index = 0
        self.colors = [
            "31",  # Red
            "32",  # Green
            "33",  # Yellow
            "34",  # Blue
            "35",  # Magenta
            "36",  # Cyan
        ]

    def next(self) -> str:
        color = self.colors[self.index]
        self.index = (self.index + 1) % len(self.colors)
        return color

    def start(self, ansi_enabled: bool = True) -> str:
        return f"\x1b[{self.next()}m" if ansi_enabled else ""

    def end(self, ansi_enabled: bool = True) -> str:
        return "\x1b[0m" if ansi_enabled else ""


class ParallelTask(PoeTask):
    """
    A task consisting of multiple tasks that run in parallel
    """

    content: list[str | dict[str, Any]]

    __key__ = "parallel"
    __content_type__: ClassVar[type] = list

    colors = ColorCycle()

    class TaskOptions(PoeTask.TaskOptions):
        ignore_fail: Literal[True, False, "return_zero", "return_non_zero"] = False
        default_item_type: str | None = None
        prefix: str | Literal[False] = "{name}"
        prefix_max: int = 16
        prefix_template: str = "{color_start}{prefix}{color_end} | "

        def validate(self):
            """
            Validation rules that don't require any extra context go here.
            """
            super().validate()
            if self.default_item_type is not None and not PoeTask.is_task_type(
                self.default_item_type, content_type=str
            ):
                raise ConfigValidationError(
                    "Unsupported value for option `default_item_type`,\n"
                    f"Expected one of {PoeTask.get_task_types(content_type=str)}"
                )
            if self.capture_stdout is not None:
                raise ConfigValidationError(
                    "Unsupported option for parallel task `capture_stdout`"
                )

    class TaskSpec(PoeTask.TaskSpec):
        content: list
        options: "ParallelTask.TaskOptions"
        subtasks: "Sequence[PoeTask.TaskSpec]"

        def __init__(
            self,
            name: str,
            task_def: dict[str, Any],
            factory: "TaskSpecFactory",
            source: "ConfigPartition",
            *,
            parent: Union["PoeTask.TaskSpec", None] = None,
        ):
            super().__init__(name, task_def, factory, source, parent=parent)

            self.subtasks = []
            for index, sub_task_def in enumerate(task_def[ParallelTask.__key__]):
                if not isinstance(sub_task_def, (str, dict, list)):
                    raise ConfigValidationError(
                        f"Item #{index} in parallel task should be a value of "
                        "type: str | dict | list",
                        task_name=self.name,
                    )

                subtask_name = (
                    sub_task_def
                    if (
                        isinstance(sub_task_def, str)
                        and (sub_task_def[0].isalpha() or sub_task_def[0] == "_")
                    )
                    else ParallelTask._subtask_name(name, index)
                )
                task_type_key = self.task_type.resolve_task_type(
                    sub_task_def,
                    factory.config,
                    array_item=task_def.get("default_item_type", True),
                )

                try:
                    self.subtasks.append(
                        factory.get(
                            subtask_name, sub_task_def, task_type_key, parent=self
                        )
                    )
                except PoeException as error:
                    raise ConfigValidationError(
                        f"Failed to interpret subtask #{index + 1} in parallel",
                        task_name=self.name,
                    ) from error

        def _task_validations(self, config: "PoeConfig", task_specs: "TaskSpecFactory"):
            """
            Perform validations on this TaskSpec that apply to a specific task type
            """
            for subtask in self.subtasks:
                if subtask.has_args:
                    raise ConfigValidationError(
                        "Unsupported option 'args' for task declared inside parallel"
                    )

                subtask.validate(config, task_specs)

    spec: TaskSpec

    def __init__(
        self,
        spec: TaskSpec,
        invocation: tuple[str, ...],
        ctx: TaskContext,
        capture_stdout: bool = False,
    ):
        assert capture_stdout in (False, None)
        super().__init__(spec, invocation, ctx)
        self._subtasks = [
            task_spec.create_task(
                invocation=(self._subtask_name(task_spec.name, index),),
                ctx=TaskContext.from_task(self, task_spec),
            )
            for index, task_spec in enumerate(spec.subtasks)
        ]

    async def _handle_run(
        self, context: "RunContext", env: "EnvVarsManager", task_state: "PoeTaskRun"
    ):
        named_arg_values, _ = self.get_parsed_arguments(env)
        env.update(named_arg_values)

        if not named_arg_values and any(arg.strip() for arg in self.invocation[1:]):
            raise PoeException(f"Parallel task {self.name!r} does not accept arguments")

        if len(self._subtasks) > 1:
            # Indicate on the global context that there are multiple stages
            context.multistage = True

        ignore_fail = self.spec.options.ignore_fail
        if ignore_fail in (True, "return_zero"):
            task_state.ignore_failure()

        task_group = DynamicTaskSet()
        task_group.create_task(
            self._handle_task_failures(task_state),
            name="handle_task_failures:" + self.name,
        )

        with context.output_streaming(enabled=True) as streaming_enabled:
            for subtask in self._subtasks:
                subtask_run: PoeTaskRun | None = None
                try:
                    subtask_run = await subtask.run(context=context, parent_env=env)
                    await task_state.add_child(subtask_run)
                except ExecutionError as error:
                    if ignore_fail:
                        self.ctx.io.print_warning(error.msg, message_verbosity=0)
                    else:
                        raise ExecutionError(
                            "Parallel task aborted after failed subtask "
                            f"{subtask.name!r}"
                        ) from error

            await task_state.finalize()

            if streaming_enabled:
                # Only collect outputs if output streaming wasn't already enabled
                # This avoids double output collection in nested parallel tasks
                task_group.create_task(
                    self._collect_output_streams(task_state, task_group),
                    name="collect_output_streams:" + self.name,
                )

            try:
                await task_group.wait()
                if exception := task_group.exception():
                    raise exception
            except Exception as error:
                self.ctx.io.print_debug(
                    " x Killing parallel task %r due to error: %r", self.name, error
                )
                raise

    async def _handle_task_failures(self, task_state: "PoeTaskRun"):
        ignore_fail = self.spec.options.ignore_fail
        non_zero_subtasks = []
        # listen for completion and error events from subtasks
        async for event in task_state.events():
            if isinstance(event, PoeTaskRunError):
                if event.exception is None:
                    self.ctx.io.print_warning(
                        "Parallel subtask %r failed with non-zero exit status",
                        event.name,
                        message_verbosity=0,
                    )
                else:
                    self.ctx.io.print_warning(
                        "Parallel subtask %r failed with exception: %s",
                        event.name,
                        event.exception,
                        message_verbosity=0,
                    )

                if not ignore_fail:
                    task_state.force_failure()
                    raise ExecutionError(
                        f"Parallel task {self.name!r} aborted after failed subtask "
                        f"{event.name!r}"
                    )
                non_zero_subtasks.append(event.name)

        if non_zero_subtasks and ignore_fail == "return_non_zero":
            task_state.force_failure()
            plural = "s" if len(non_zero_subtasks) > 1 else ""
            raise ExecutionError(
                f"Subtask{plural} {', '.join(repr(st) for st in non_zero_subtasks)} "
                "returned non-zero exit status"
            )

    async def _collect_output_streams(
        self, task_state: PoeTaskRun, task_group: DynamicTaskSet
    ):
        async for task_run, subproc in task_state.processes():
            subtask_index = task_state.get_child_index(task_run)
            task_group.create_task(
                self._format_output_lines(task_run.name, subtask_index, subproc),
                name=f"format_output_lines:{task_run.name}",
            )

    async def _format_output_lines(
        self, task_name: str, subtask_index: int, subproc: "Process"
    ):
        if not subproc.stdout:
            return

        try:
            options = self.spec.options
            if options.prefix:
                prefix_content = options.prefix.format(
                    name=task_name, index=subtask_index
                )
                if len(prefix_content) > options.prefix_max:
                    prefix_content = prefix_content[: options.prefix_max - 1] + "…"
                ansi_enabled = self.ctx.io.ansi_enabled
                prefix = options.prefix_template.format(
                    prefix=prefix_content,
                    color_start=self.colors.start(ansi_enabled),
                    color_end=self.colors.end(ansi_enabled),
                ).encode("utf-8", errors="replace")
            else:
                prefix = b""
        except Exception as error:
            self.ctx.io.print_warning(
                "Failed to format prefix for parallel subtask '%s': %s",
                task_name,
                error,
            )
            prefix = b""

        write = sys.stdout.buffer.write
        flush = sys.stdout.flush
        if prefix:
            while line := await subproc.stdout.readline():
                write(prefix)
                write(line)
                flush()
        else:
            while line := await subproc.stdout.readline():
                write(line)
                flush()

    @classmethod
    def _subtask_name(cls, task_name: str, index: int):
        return f"{task_name}[{index}]"
