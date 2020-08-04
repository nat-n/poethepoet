from pathlib import Path
from typing import Any, Dict, Generator, Iterable, MutableMapping, Type, TYPE_CHECKING
from .base import PoeTask

if TYPE_CHECKING:
    from ..config import PoeConfig


class ScriptTask(PoeTask):
    """
    A task consisting of a reference to a python script
    """

    content: str

    __key__ = "script"
    __options__: Dict[str, Type] = {}

    def _handle_run(
        self,
        extra_args: Iterable[str],
        project_dir: Path,
        env: MutableMapping[str, str],
        dry: bool = False,
        subproc_only: bool = False,
    ) -> Generator[Dict[str, Any], int, int]:
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
        yield {"cmd": cmd}
        return 0
