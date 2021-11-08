from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)
from .base import PoeTask, TaskContent
from ..exceptions import ExecutionError, PoeException

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext
    from ..executor import PoeExecutor
    from ..ui import PoeUi


class SequenceTask(PoeTask):
    """
    A task consisting of a sequence of other tasks
    """

    content: List[Union[str, Dict[str, Any]]]

    __key__ = "sequence"
    __content_type__: Type = list
    __options__: Dict[str, Union[Type, Tuple[Type, ...]]] = {
        "ignore_fail": (bool, str),
        "default_item_type": str,
    }

    def __init__(
        self,
        name: str,
        content: TaskContent,
        options: Dict[str, Any],
        ui: "PoeUi",
        config: "PoeConfig",
        invocation: Tuple[str, ...],
        capture_stdout: bool = False,
    ):
        assert capture_stdout == False
        super().__init__(name, content, options, ui, config, invocation)

        self.subtasks = [
            self.from_def(
                task_def=item,
                task_name=task_name,
                config=config,
                invocation=(task_name,),
                ui=ui,
                array_item=self.options.get("default_item_type", True),
            )
            for index, item in enumerate(self.content)
            for task_name in (item if isinstance(item, str) else f"{name}[{index}]",)
        ]

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: Mapping[str, str],
    ) -> int:
        env, has_named_args = self.add_named_args_to_env(env)

        if not has_named_args and any(arg.strip() for arg in extra_args):
            raise PoeException(f"Sequence task {self.name!r} does not accept arguments")

        if len(self.subtasks) > 1:
            # Indicate on the global context that there are multiple stages
            context.multistage = True

        ignore_fail = self.options.get("ignore_fail")
        non_zero_subtasks: List[str] = list()
        for subtask in self.subtasks:
            task_result = subtask.run(context=context, extra_args=tuple(), env=env)
            if task_result and not ignore_fail:
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
    def _validate_task_def(
        cls, task_name: str, task_def: Dict[str, Any], config: "PoeConfig"
    ) -> Optional[str]:
        default_item_type = task_def.get("default_item_type")
        if default_item_type is not None and not cls.is_task_type(
            default_item_type, content_type=str
        ):
            return (
                "Unsupported value for option `default_item_type` for task "
                f"{task_name!r}. Expected one of {cls.get_task_types(content_type=str)}"
            )
        ignore_fail = task_def.get("ignore_fail")
        if ignore_fail is not None and ignore_fail not in (
            True,
            False,
            "return_zero",
            "return_non_zero",
        ):
            return (
                "Unsupported value for option `ignore_fail` for task "
                f'{task_name!r}. Expected one of (true, false, "return_zero", "return_non_zero")'
            )

        return None
