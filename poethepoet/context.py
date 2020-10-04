from pathlib import Path
from typing import (
    Any,
    Dict,
    MutableMapping,
    Optional,
    TYPE_CHECKING,
)
from .executor import PoeExecutor

if TYPE_CHECKING:
    from .config import PoeConfig


class RunContext:
    config: "PoeConfig"
    env: Dict[str, str]
    dry: bool
    poe_active: Optional[str]
    project_dir: Path
    multistage: bool = False
    exec_cache: Dict[str, Any]

    def __init__(
        self,
        config: "PoeConfig",
        env: MutableMapping[str, str],
        dry: bool,
        poe_active: Optional[str],
    ):
        self.config = config
        self.project_dir = Path(config.project_dir)
        self.env = {**env, "POE_ROOT": str(config.project_dir)}
        self.dry = dry
        self.poe_active = poe_active
        self.exec_cache = {}

    def get_env(self, env: MutableMapping[str, str]) -> Dict[str, str]:
        return {**self.env, **env}

    def get_executor(
        self,
        env: MutableMapping[str, str],
        task_executor: Optional[Dict[str, str]] = None,
    ) -> PoeExecutor:
        return PoeExecutor.get(
            context=self,
            env=self.get_env(env),
            working_dir=self.project_dir,
            dry=self.dry,
            executor_config=task_executor,
        )
