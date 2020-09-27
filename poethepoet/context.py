from pathlib import Path
from typing import (
    Any,
    Dict,
    MutableMapping,
    Optional,
    Type,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from .executor import PoeExecutor


class RunContext:
    project_dir: Path
    executor_cls: Type["PoeExecutor"]
    env: Dict[str, str]
    dry: bool
    poe_active: Optional[str]
    multistage: bool = False
    exec_cache: Dict[str, Any]

    def __init__(
        self,
        project_dir: Path,
        executor_cls: Type["PoeExecutor"],
        env: MutableMapping[str, str],
        dry: bool,
        poe_active: Optional[str],
    ):
        self.project_dir = project_dir
        self.executor_cls = executor_cls
        self.env = {**env, "POE_ROOT": str(project_dir)}
        self.dry = dry
        self.poe_active = poe_active
        self.exec_cache = {}

    def get_env(self, env: MutableMapping[str, str]) -> Dict[str, str]:
        return {**self.env, **env}

    def get_executor(self, env: MutableMapping[str, str]) -> "PoeExecutor":
        return self.executor_cls(
            context=self,
            env=self.get_env(env),
            working_dir=self.project_dir,
            dry=self.dry,
        )
