import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from .config import PoeConfig
    from .env.manager import EnvVarsManager
    from .executor import PoeExecutor
    from .ui import PoeUi


class RunContext:
    config: "PoeConfig"
    ui: "PoeUi"
    env: "EnvVarsManager"
    dry: bool
    poe_active: Optional[str]
    project_dir: Path
    multistage: bool = False
    exec_cache: dict[str, Any]
    captured_stdout: dict[tuple[str, ...], str]

    def __init__(
        self,
        config: "PoeConfig",
        ui: "PoeUi",
        env: Mapping[str, str],
        dry: bool,
        poe_active: Optional[str],
        multistage: bool = False,
        cwd: Optional[Union[Path, str]] = None,
    ):
        from .env.manager import EnvVarsManager

        self.config = config
        self.ui = ui
        self.project_dir = Path(config.project_dir)
        self.dry = dry
        self.poe_active = poe_active
        self.multistage = multistage
        self.exec_cache = {}
        self.captured_stdout = {}

        # Init root EnvVarsManager
        self.env = EnvVarsManager(self.config, self.ui, base_env=env, cwd=cwd)
        for config_part in self.config.partitions():
            self.env.apply_env_config(
                envfile=config_part.get("envfile", None),
                config_env=config_part.get("env", None),
                config_dir=config_part.config_dir,
                config_working_dir=config_part.cwd,
            )

    def _get_dep_values(
        self, used_task_invocations: Mapping[str, tuple[str, ...]]
    ) -> dict[str, str]:
        """
        Get env vars from upstream tasks declared via the uses option.
        """
        return {
            var_name: self.get_task_output(invocation)
            for var_name, invocation in used_task_invocations.items()
        }

    def save_task_output(self, invocation: tuple[str, ...], captured_stdout: bytes):
        """
        Store the stdout data from a task so that it can be reused by other tasks
        """
        try:
            self.captured_stdout[invocation] = captured_stdout.decode()
        except UnicodeDecodeError:
            # Attempt to recover in case a specific encoding is configured
            io_encoding = self.env.get("PYTHONIOENCODING")
            if io_encoding:
                self.captured_stdout[invocation] = captured_stdout.decode(io_encoding)
            else:
                raise

    def get_task_output(self, invocation: tuple[str, ...]):
        """
        Get the stored stdout data from a task so that it can be reused by other tasks

        New lines are replaced with whitespace similar to how unquoted command
        interpolation works in bash.
        """
        return re.sub(r"\s+", " ", self.captured_stdout[invocation].strip("\r\n"))

    def get_executor(
        self,
        invocation: tuple[str, ...],
        env: "EnvVarsManager",
        working_dir: Path,
        *,
        executor_config: Optional[Mapping[str, str]] = None,
        capture_stdout: Union[str, bool] = False,
        delegate_dry_run: bool = False,
    ) -> "PoeExecutor":
        """
        Get an Executor object for use with this invocation.

        if delegate_dry_run is set then the task will always be executed and be
        entrusted to not have any side effects when the dry-run flag is set.
        """

        from .executor import PoeExecutor

        if not executor_config:
            if self.ui["executor"]:
                executor_config = {"type": self.ui["executor"]}
            else:
                executor_config = self.config.executor

        return PoeExecutor.get(
            invocation=invocation,
            context=self,
            executor_config=executor_config,
            env=env,
            working_dir=working_dir,
            capture_stdout=capture_stdout,
            dry=False if delegate_dry_run else self.dry,
        )
