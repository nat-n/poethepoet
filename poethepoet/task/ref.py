import shlex
from typing import (
    Any,
    Dict,
    Mapping,
    Optional,
    Sequence,
    Type,
    Tuple,
    TYPE_CHECKING,
    Union,
)
from .base import PoeTask
from ..helpers.env import resolve_envvars

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
        env: Mapping[str, str],
    ) -> int:
        """
        Lookup and delegate to the referenced task
        """
        invocation = tuple(shlex.split(resolve_envvars(self.content, env)))
        task = self.from_config(invocation[0], self._config, self._ui, invocation)
        return task.run(context=context, extra_args=extra_args, env=env)

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

        return None
