from pathlib import Path
from typing import Dict, Iterable, MutableMapping, Optional, Type
import sys
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
        from poetry.factory import Factory
        from poetry.masonry.utils.module import Module

        poetry = Factory().create_poetry(project_dir)
        package = poetry.package
        poetry_module = Module(
            package.name, poetry.file.parent.as_posix(), package.packages
        )
        src_in_sys_path = (  # poetry run does this so we do too
            "sys.path.append('src'); " if poetry_module.is_in_src() else ""
        )
        target_module, target_callable = self.content.split(":")
        argv = [self.name, *(self._resolve_envvars(token, env) for token in extra_args)]
        cmd = (
            sys.executable,
            "-c",
            "import sys; "
            "from importlib import import_module; "
            f"sys.argv = {argv!r}; {src_in_sys_path}"
            f"import_module('{target_module}').{target_callable}()",
        )
        self._print_action(" ".join(argv), dry)
        if dry:
            # Don't actually run anything...
            return
        self._execute(project_dir, cmd, env)

    @classmethod
    def _validate_task_def(cls, task_def: TaskDef) -> Optional[str]:
        """
        Check the given task definition for validity specific to this task type and
        return a message describing the first encountered issue if any.
        """
        issue = None
        return issue
