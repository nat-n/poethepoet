from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

from ..exceptions import ConfigValidationError, ExecutionError, PoeException
from .base import PoeTask, TaskContext

if TYPE_CHECKING:
    from ..config import ConfigPartition, PoeConfig
    from ..context import RunContext
    from ..env.manager import EnvVarsManager
    from .base import TaskSpecFactory


class SequenceTask(PoeTask):
    """
    A task consisting of a sequence of other tasks
    """

    content: List[Union[str, Dict[str, Any]]]

    __key__ = "sequence"
    __content_type__: ClassVar[Type] = list

    class TaskOptions(PoeTask.TaskOptions):
        ignore_fail: Literal[True, False, "return_zero", "return_non_zero"] = False
        default_item_type: Optional[str] = None

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

    class TaskSpec(PoeTask.TaskSpec):
        content: list
        options: "SequenceTask.TaskOptions"
        subtasks: Sequence[PoeTask.TaskSpec]

        def __init__(
            self,
            name: str,
            task_def: Dict[str, Any],
            factory: "TaskSpecFactory",
            parent: Optional["PoeTask.TaskSpec"] = None,
            source: Optional["ConfigPartition"] = None,
        ):
            super().__init__(name, task_def, factory, parent, source)

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
                    if isinstance(sub_task_def, str)
                    else SequenceTask._subtask_name(name, index)
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
                        f"Failed to interpret subtask #{index} in sequence",
                        task_name=self.name,
                    )

        def _task_validations(self, config: "PoeConfig", task_specs: "TaskSpecFactory"):
            """
            Perform validations on this TaskSpec that apply to a specific task type
            """
            for index, subtask in enumerate(self.subtasks):
                if subtask.args:
                    raise ConfigValidationError(
                        "Unsupported option 'args' for task declared inside sequence"
                    )

                subtask.validate(config, task_specs)

    spec: TaskSpec

    def __init__(
        self,
        spec: TaskSpec,
        invocation: Tuple[str, ...],
        ctx: TaskContext,
        capture_stdout: bool = False,
    ):
        assert capture_stdout in (False, None)
        super().__init__(spec, invocation, ctx)

        self.subtasks = [
            task_spec.create_task(
                invocation=(task_spec.name,),  # FIXME: this looks wrong!
                ctx=TaskContext.from_task(self),
            )
            for task_spec in spec.subtasks
        ]

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: "EnvVarsManager",
    ) -> int:
        named_arg_values = self.get_named_arg_values(env)
        env.update(named_arg_values)

        if not named_arg_values and any(arg.strip() for arg in extra_args):
            raise PoeException(f"Sequence task {self.name!r} does not accept arguments")

        if len(self.subtasks) > 1:
            # Indicate on the global context that there are multiple stages
            context.multistage = True

        ignore_fail = self.spec.options.ignore_fail
        non_zero_subtasks: List[str] = list()
        for subtask in self.subtasks:
            task_result = subtask.run(
                context=context, extra_args=tuple(), parent_env=env
            )
            if task_result and not ignore_fail:
                print("subtask", subtask, subtask.name)
                raise ExecutionError(
                    f"Sequence aborted after failed subtask {subtask.name!r}"
                )
            if task_result:
                non_zero_subtasks.append(subtask.name)

        if non_zero_subtasks and ignore_fail == "return_non_zero":
            raise ExecutionError(
                f"Subtasks {', '.join(non_zero_subtasks)} returned non-zero exit status"
            )
        return 0

    @classmethod
    def _subtask_name(cls, task_name: str, index: int):
        return f"{task_name}[{index}]"
