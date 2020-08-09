from pathlib import Path
import re
from typing import (
    Any,
    Dict,
    Iterable,
    Optional,
    MutableMapping,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)
from .base import PoeTask

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..executor import PoeExecutor


_FUNCTION_CALL_PATTERN = re.compile(r"^(.+)\((.*)\)\s*;?\s*$")


class ScriptTask(PoeTask):
    """
    A task consisting of a reference to a python script
    """

    content: str

    __key__ = "script"
    __options__: Dict[str, Type] = {}

    def _handle_run(
        self,
        executor: "PoeExecutor",
        extra_args: Iterable[str],
        project_dir: Path,
        env: MutableMapping[str, str],
        dry: bool = False,
    ) -> int:
        # TODO: check whether the project really does use src layout, and don't do
        #       sys.path.append('src') if it doesn't
        target_module, target_call = self._parse_content(self.content)
        argv = [self.name, *(self._resolve_envvars(token, env) for token in extra_args)]
        cmd = (
            "python",  # TODO: pre-locate python from the target env?
            "-c",
            "import sys; "
            "from importlib import import_module; "
            f"sys.argv = {argv!r}; sys.path.append('src');"
            f"import_module('{target_module}').{target_call}",
        )
        self._print_action(" ".join(argv), dry)
        return executor.execute(cmd)

    @classmethod
    def _parse_content(cls, call_ref: str) -> Union[Tuple[str, str], Tuple[None, None]]:
        """
        Parse module and callable call out of a string like one of:
         - "some_module:main"
         - "some.module:main(foo='bar')"
        """
        try:
            target_module, target_ref = call_ref.split(":")
        except ValueError:
            return None, None

        if target_ref.isidentifier():
            return target_module, f"{target_ref}()"

        call_match = _FUNCTION_CALL_PATTERN.match(target_ref)
        if call_match:
            callable_name, call_params = call_match.groups()
            return target_module, f"{callable_name}({call_params})"

        return None, None

    @classmethod
    def _validate_task_def(
        cls, task_name: str, task_def: Dict[str, Any], config: "PoeConfig"
    ) -> Optional[str]:
        target_module, target_call = cls._parse_content(task_def["script"])
        if not target_module or not target_call:
            return (
                f"Task {task_name!r} contains invalid callable reference "
                f"{task_def['script']!r} (expected something like `module:callable()`)"
            )
        return None
