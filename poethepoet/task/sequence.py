from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    MutableMapping,
    Optional,
    Type,
    TYPE_CHECKING,
    Union,
)
from .base import PoeTask, TaskContent
from ..exceptions import ExecutionError, PoeException

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..executor import PoeExecutor
    from ..ui import PoeUi


class SequenceTask(PoeTask):
    """
    A task consisting of a sequence of other tasks
    """

    content: List[Union[str, Dict[str, Any]]]

    __key__ = "sequence"
    __content_type__: Type = list
    __options__: Dict[str, Type] = {"ignore_fail": bool, "default_item_type": str}

    def __init__(
        self,
        name: str,
        content: TaskContent,
        options: Dict[str, Any],
        ui: "PoeUi",
        config: "PoeConfig",
    ):
        super().__init__(name, content, options, ui, config)
        self.subtasks = [
            self.from_def(
                task_def=item,
                task_name=item if isinstance(item, str) else f"{name}[{index}]",
                config=config,
                ui=ui,
                array_item=self.options.get("default_item_type", True),
            )
            for index, item in enumerate(self.content)
        ]

    def _handle_run(
        self,
        executor: "PoeExecutor",
        extra_args: Iterable[str],
        project_dir: Path,
        env: MutableMapping[str, str],
        dry: bool = False,
    ) -> int:
        if any(arg.strip() for arg in extra_args):
            raise PoeException(f"Sequence task {self.name!r} does not accept arguments")
        for subtask in self.subtasks:
            task_result = subtask.run(
                extra_args=tuple(), project_dir=project_dir, env=env, dry=dry,
            )
            if task_result and not self.options.get("ignore_fail"):
                raise ExecutionError(
                    f"Sequence aborted after failed subtask {subtask.name!r}"
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
        return None
