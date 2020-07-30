from pathlib import Path
from typing import Dict, Iterable, MutableMapping, Optional, Type
from .base import PoeTask, TaskDef


class ScriptTask(PoeTask):
    """
    A task consisting of a reference to a python script
    """

    __key__ = "script"
    __options__: Dict[str, Type] = {}

    def _handle_run(
        self,
        extra_args: Iterable[str],
        project_dir: Path,
        env: MutableMapping[str, str],
        dry: bool = False,
    ):
        # TODO: check whether the project really does use src layout, and don't do
        #       sys.path.append('src') if it doesn't
        target_module, target_callable = self.content.split(":")
        argv = [self.name, *(self._resolve_envvars(token, env) for token in extra_args)]
        cmd = (
            "python",  # TODO: pre-locate python from the target env
            "-c",
            "import sys; "
            "from importlib import import_module; "
            f"sys.argv = {argv!r}; sys.path.append('src');"
            f"import_module('{target_module}').{target_callable}()",
        )
        self._print_action(" ".join(argv), dry)
        if dry:
            # Don't actually run anything...
            return 0
        return self._execute(project_dir, cmd, env)

    @classmethod
    def _validate_task_def(cls, task_def: TaskDef) -> Optional[str]:
        """
        Check the given task definition for validity specific to this task type and
        return a message describing the first encountered issue if any.
        """
        issue = None
        return issue
