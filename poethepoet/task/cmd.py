from glob import glob
from pathlib import Path
import re
import shlex
from typing import Dict, Iterable, MutableMapping, Optional, Type
from .base import PoeTask, TaskDef

_GLOBCHARS_PATTERN = re.compile(r".*[\*\?\[]")


class CmdTask(PoeTask):
    """
    A task consisting of a reference to a shell command
    """

    __key__ = "cmd"
    __options__: Dict[str, Type] = {}

    def _handle_run(
        self,
        extra_args: Iterable[str],
        project_dir: Path,
        env: MutableMapping[str, str],
        dry: bool = False,
    ):
        cmd = self._resolve_args(extra_args, env)
        self._print_action(" ".join(cmd), dry)
        if dry:
            # Don't actually run anything...
            return
        self._execute(project_dir, cmd, env)

    def _resolve_args(self, extra_args: Iterable[str], env: MutableMapping[str, str]):
        # Parse shell command tokens
        cmd_tokens = shlex.split(
            self._resolve_envvars(self.content, env), comments=True
        )
        extra_args = [self._resolve_envvars(token, env) for token in extra_args]
        # Resolve any glob pattern paths
        result = []
        for cmd_token in (*cmd_tokens, *extra_args):
            if _GLOBCHARS_PATTERN.match(cmd_token):
                # looks like a glob path so resolve it
                result.extend(glob(cmd_token, recursive=True))
            else:
                result.append(cmd_token)
        # Finally add the extra_args from the invoking command and we're done
        return result

    @classmethod
    def _validate_task_def(cls, task_def: TaskDef) -> Optional[str]:
        """
        Check the given task definition for validity specific to this task type and
        return a message describing the first encountered issue if any.
        """
        issue = None
        return issue
