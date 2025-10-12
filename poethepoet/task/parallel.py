import asyncio
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypeVar, Union

from ..exceptions import ConfigValidationError, ExecutionError, PoeException
from ..executor.task_run import PoeTaskRun, PoeTaskRunError
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

    def start(self) -> str:
        return f"\x1b[{self.next()}m"

    def end(self) -> str:
        return "\x1b[0m"


class ParallelTask(PoeTask):
    """
    A task consisting of multiple tasks that run in parallel
    """

    content: list[Union[str, dict[str, Any]]]

    __key__ = "parallel"
    __content_type__: ClassVar[type] = list

    colors = ColorCycle()

    class TaskOptions(PoeTask.TaskOptions):
        ignore_fail: Literal[True, False, "return_zero", "return_non_zero"] = False
        default_item_type: Union[str, None] = None

        prefix: str = "{name}"
        prefix_max: int = 16
        prefix_template: str = "{color_start}{prefix}{color_end} |"

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
                except PoeException:
                    raise ConfigValidationError(
                        f"Failed to interpret subtask #{index} in parallel",
                        task_name=self.name,
                    )

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
        """
        TODO: OUTPUT modes
        - multiplex with line prefix
        - no capture
        - override capture on inline task? (include ref tasks)
        """

        named_arg_values, extra_args = self.get_parsed_arguments(env)
        env.update(named_arg_values)

        if not named_arg_values and any(arg.strip() for arg in self.invocation[1:]):
            raise PoeException(f"Parallel task {self.name!r} does not accept arguments")

        if len(self._subtasks) > 1:
            # Indicate on the global context that there are multiple stages
            context.multistage = True

        ignore_fail = self.spec.options.ignore_fail
        if ignore_fail in (True, "return_zero"):
            task_state.ignore_failure()

        futures: list[asyncio.Task] = []
        futures.append(asyncio.create_task(self._handle_task_failures(task_state)))
        futures.append(
            asyncio.create_task(self._collect_output_streams(task_state, futures))
        )

        with context.output_streaming(enabled=True):
            for subtask in self._subtasks:
                subtask_run: Union[PoeTaskRun, None] = None
                try:
                    subtask_run = await subtask.run(context=context, parent_env=env)
                    await task_state.add_child(subtask_run)
                except ExecutionError as error:
                    if ignore_fail:
                        self.ctx.io.print_warning(error.msg, message_verbosity=0)
                    else:
                        raise

            await task_state.finalize()

            try:
                await asyncio.gather(*futures)
            except ExecutionError:
                pass  # already handled in _handle_task_failures
            except Exception as error:
                await task_state.kill()
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
                    await task_state.kill()
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
        self, task_state: PoeTaskRun, line_formatting_tasks: list[asyncio.Task]
    ):
        async for name, subproc in task_state.processes():
            line_formatting_tasks.append(
                asyncio.create_task(self._format_output_lines(name, subproc))
            )

    async def _format_output_lines(self, task_name: str, subproc: "Process"):
        if subproc.stdout:
            prefix_content = self.spec.options.prefix.format(name=task_name)
            if len(prefix_content) > self.spec.options.prefix_max:
                prefix_content = (
                    prefix_content[: self.spec.options.prefix_max - 1] + "…"
                )
            prefix = self.spec.options.prefix_template.format(
                prefix=prefix_content,
                color_start=self.colors.start(),
                color_end=self.colors.end(),
            )
            while line := await subproc.stdout.readline():
                print(prefix, line.decode(), end="", flush=True)

    @classmethod
    def _subtask_name(cls, task_name: str, index: int):
        return f"{task_name}[{index}]"
