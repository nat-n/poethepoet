from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    MutableMapping,
    Optional,
    Type,
    TYPE_CHECKING,
)
from .base import PoeTask

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..executor import PoeExecutor


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
        executor: "PoeExecutor",
        extra_args: Iterable[str],
        project_dir: Path,
        env: MutableMapping[str, str],
        dry: bool = False,
    ) -> int:
        """
        Lookup and delegate to the referenced task
        """
        task = self.from_config(self.content, self._config, ui=self._ui)
        return task.run(
            extra_args=extra_args, project_dir=project_dir, env=env, dry=dry,
        )

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
