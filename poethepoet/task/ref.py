from typing import (
    Any,
    Dict,
    MutableMapping,
    Optional,
    Sequence,
    Type,
    TYPE_CHECKING,
)
from .base import PoeTask

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext


class RefTask(PoeTask):
    """
    A task consisting of a reference to another task
    """

    # TODO: support extending/overriding env or other configuration of the referenced task

    content: str

    __key__ = "ref"
    __options__: Dict[str, Type] = {}

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: MutableMapping[str, str],
    ) -> int:
        """
        Lookup and delegate to the referenced task
        """
        task = self.from_config(
            self.content, self._config, ui=self._ui, invocation=(self.content,)
        )
        return task.run(context=context, extra_args=extra_args, env=env,)

    @classmethod
    def _validate_task_def(
        cls, task_name: str, task_def: Dict[str, Any], config: "PoeConfig"
    ) -> Optional[str]:
        """
        Check the given task definition for validity specific to this task type and
        return a message describing the first encountered issue if any.
        """
        if task_def["ref"] not in config.tasks:
            return f"Task {task_name!r} contains reference to unkown task {task_def['ref']!r}"

        return None
