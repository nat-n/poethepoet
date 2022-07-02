import shlex
from typing import (
    Any,
    Dict,
    Optional,
    Sequence,
    Type,
    Tuple,
    TYPE_CHECKING,
    Union,
)
from .base import PoeTask
from ..env.manager import EnvVarsManager

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext


class RefTask(PoeTask):
    """
    A task consisting of a reference to another task
    """

    content: str

    __key__ = "ref"
    __options__: Dict[str, Union[Type, Tuple[Type, ...]]] = {}

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: EnvVarsManager,
    ) -> int:
        """
        Lookup and delegate to the referenced task
        """
        invocation = tuple(shlex.split(env.fill_template(self.content.strip())))
        task = self.from_config(invocation[0], self._config, self._ui, invocation)
        return task.run(context=context, extra_args=extra_args, parent_env=env)

    @classmethod
    def _validate_task_def(
        cls, task_name: str, task_def: Dict[str, Any], config: "PoeConfig"
    ) -> Optional[str]:
        """
        Check the given task definition for validity specific to this task type and
        return a message describing the first encountered issue if any.
        """
        task_ref = task_def["ref"]

        if shlex.split(task_ref)[0] not in config.tasks:
            return f"Task {task_name!r} contains reference to unkown task {task_ref!r}"

        referenced_task = config.tasks[task_ref]
        if isinstance(referenced_task, dict) and referenced_task.get("use_exec"):
            return (
                f"Invalid task: {task_name!r}. contains illegal reference to task with "
                f"use_exec set to true: {task_ref!r}"
            )

        return None
