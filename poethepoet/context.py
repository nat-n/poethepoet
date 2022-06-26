from pathlib import Path
import re
from typing import (
    Any,
    Dict,
    Mapping,
    Optional,
    Tuple,
    TYPE_CHECKING,
)
from .executor import PoeExecutor
from .env.manager import EnvVarsManager

if TYPE_CHECKING:
    from .config import PoeConfig
    from .ui import PoeUi


class RunContext:
    config: "PoeConfig"
    ui: "PoeUi"
    env: EnvVarsManager
    dry: bool
    poe_active: Optional[str]
    project_dir: Path
    multistage: bool = False
    exec_cache: Dict[str, Any]
    captured_stdout: Dict[Tuple[str, ...], str]

    def __init__(
        self,
        config: "PoeConfig",
        ui: "PoeUi",
        env: Mapping[str, str],
        dry: bool,
        poe_active: Optional[str],
        multistage: bool = False,
    ):
        self.config = config
        self.ui = ui
        self.project_dir = Path(config.project_dir)
        self.dry = dry
        self.poe_active = poe_active
        self.multistage = multistage
        self.exec_cache = {}
        self.captured_stdout = {}
        self.env = EnvVarsManager(self.config, self.ui, base_env=env)

    @property
    def executor_type(self) -> Optional[str]:
        return self.config.executor["type"]

    def get_task_env(
        self,
        parent_env: Optional[EnvVarsManager],
        task_envfile: Optional[str],
        task_env: Optional[Mapping[str, str]],
        task_uses: Optional[Mapping[str, Tuple[str, ...]]] = None,
    ) -> EnvVarsManager:
        if parent_env is None:
            parent_env = self.env

        result = parent_env.for_task(task_envfile, task_env)

        # Include env vars from dependencies
        if task_uses is not None:
            result.update(self.get_dep_values(task_uses))

        return result

    def get_dep_values(
        self, used_task_invocations: Mapping[str, Tuple[str, ...]]
    ) -> Dict[str, str]:
        """
        Get env vars from upstream tasks declared via the uses option.

        New lines are replaced with whitespace similar to how unquoted command
        interpolation works in bash.
        """
        return {
            var_name: re.sub(
                r"\s+", " ", self.captured_stdout[invocation].strip("\r\n")
            )
            for var_name, invocation in used_task_invocations.items()
        }

    def get_executor(
        self,
        invocation: Tuple[str, ...],
        env: EnvVarsManager,
        task_options: Dict[str, Any],
    ) -> PoeExecutor:
        return PoeExecutor.get(
            invocation=invocation,
            context=self,
            env=env,
            working_dir=self.project_dir / task_options.get("cwd", "."),
            dry=self.dry,
            executor_config=task_options.get("executor"),
            capture_stdout=task_options.get("capture_stdout", False),
        )
