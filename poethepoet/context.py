from pathlib import Path
from typing import (
    Any,
    Dict,
    MutableMapping,
    Optional,
    Tuple,
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
    captured_stdout: Dict[Tuple[str, ...], str]

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
        self.captured_stdout = {}

    @property
    def executor_type(self) -> Optional[str]:
        return self.config.executor["type"]

    def get_env(self, env: MutableMapping[str, str]) -> Dict[str, str]:
        return {**self.env, **env}

    def get_executor(
        self,
        invocation: Tuple[str, ...],
        env: MutableMapping[str, str],
        task_options: Dict[str, Any],
    ) -> PoeExecutor:
        return PoeExecutor.get(
            invocation=invocation,
            context=self,
            env=self.get_env(env),
            working_dir=self.project_dir,
            dry=self.dry,
            executor_config=task_options.get("executor"),
            capture_stdout=task_options.get("capture_stdout", False),
        )
