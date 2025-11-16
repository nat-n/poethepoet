from typing import TYPE_CHECKING, Any, ClassVar, Literal, Union

from ..exceptions import ConfigValidationError, ExecutionError, PoeException
from .base import PoeTask, TaskContext

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..config import ConfigPartition, PoeConfig
    from ..context import RunContext
    from ..env.manager import EnvVarsManager
    from ..executor.task_run import PoeTaskRun
    from .base import TaskSpecFactory


class SequenceTask(PoeTask):
    """
    A task consisting of a sequence of other tasks
    """

    content: list[str | dict[str, Any]]

    __key__ = "sequence"
    __content_type__: ClassVar[type] = list

    class TaskOptions(PoeTask.TaskOptions):
        ignore_fail: Literal[True, False, "return_zero", "return_non_zero"] = False
        default_item_type: str | None = None

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
                    "Unsupported option for sequence task `capture_stdout`"
                )

    class TaskSpec(PoeTask.TaskSpec):
        content: list
        options: "SequenceTask.TaskOptions"
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
            for index, sub_task_def in enumerate(task_def[SequenceTask.__key__]):
                if not isinstance(sub_task_def, (str, dict, list)):
                    raise ConfigValidationError(
                        f"Item #{index} in sequence task should be a value of "
                        "type: str | dict | list",
                        task_name=self.name,
                    )

                subtask_name = (
                    sub_task_def
                    if (
                        isinstance(sub_task_def, str)
                        and (sub_task_def[0].isalpha() or sub_task_def[0] == "_")
                    )
                    else SequenceTask._subtask_name(name, index)
                )
                if isinstance(sub_task_def, list):
                    # Nested array interpreted as parallel task
                    task_type_key: str | None = "parallel"
                else:
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
                        f"Failed to interpret subtask #{index} in sequence",
                        task_name=self.name,
                    ) from error

        def _task_validations(self, config: "PoeConfig", task_specs: "TaskSpecFactory"):
            """
            Perform validations on this TaskSpec that apply to a specific task type
            """
            for subtask in self.subtasks:
                if subtask.has_args:
                    raise ConfigValidationError(
                        "Unsupported option 'args' for task declared inside sequence"
                    )

                subtask.validate(config, task_specs)

    spec: TaskSpec
    _subtasks: "Sequence[PoeTask]"

    def __init__(
        self,
        spec: TaskSpec,
        invocation: tuple[str, ...],
        ctx: TaskContext,
        capture_stdout: bool = False,
    ):
        assert capture_stdout in (False, None)
        super().__init__(spec, invocation, ctx)
        self._subtasks: Sequence[PoeTask] = [
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
            raise PoeException(f"Sequence task {self.name!r} does not accept arguments")

        if len(self._subtasks) > 1:
            # Indicate on the global context that there are multiple stages
            context.multistage = True

        ignore_fail = self.spec.options.ignore_fail
        if ignore_fail in (True, "return_zero"):
            task_state.ignore_failure()

        non_zero_subtasks = []
        for subtask in self._subtasks:
            subtask_run: PoeTaskRun | None = None
            try:
                subtask_run = await subtask.run(context=context, parent_env=env)
                await task_state.add_child(subtask_run)
                await subtask_run.wait(suppress_errors=False)
            except ExecutionError as error:
                if ignore_fail:
                    self.ctx.io.print_warning(error.msg, message_verbosity=0)
                else:
                    raise ExecutionError(
                        f"Sequence aborted after failed subtask {subtask.name!r}"
                    ) from error

            if not subtask_run or subtask_run.has_failure:
                if not ignore_fail:
                    raise ExecutionError(
                        f"Sequence aborted after failed subtask {subtask.name!r}"
                    )
                non_zero_subtasks.append(subtask.name)

        await task_state.finalize()

        if non_zero_subtasks and ignore_fail == "return_non_zero":
            task_state.force_failure()
            plural = "s" if len(non_zero_subtasks) > 1 else ""
            raise ExecutionError(
                f"Subtask{plural} {', '.join(repr(st) for st in non_zero_subtasks)} "
                "returned non-zero exit status"
            )

    @classmethod
    def _subtask_name(cls, task_name: str, index: int):
        return f"{task_name}[{index}]"
