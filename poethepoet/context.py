from pathlib import Path
from typing import (
    Any,
    Dict,
    MutableMapping,
    Optional,
    Tuple,
    TYPE_CHECKING,
)
from .exceptions import ExecutionError
from .executor import PoeExecutor
from .envfile import load_env_file

if TYPE_CHECKING:
    from .config import PoeConfig
    from .ui import PoeUi


class RunContext:
    config: "PoeConfig"
    ui: "PoeUi"
    env: Dict[str, str]
    dry: bool
    poe_active: Optional[str]
    project_dir: Path
    multistage: bool = False
    exec_cache: Dict[str, Any]
    captured_stdout: Dict[Tuple[str, ...], str]
    _envfile_cache: Dict[str, Dict[str, str]]

    def __init__(
        self,
        config: "PoeConfig",
        ui: "PoeUi",
        env: MutableMapping[str, str],
        dry: bool,
        poe_active: Optional[str],
    ):
        self.config = config
        self.ui = ui
        self.project_dir = Path(config.project_dir)
        self.env = {**env, "POE_ROOT": str(config.project_dir)}
        self.dry = dry
        self.poe_active = poe_active
        self.exec_cache = {}
        self.captured_stdout = {}
        self._envfile_cache = {}

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
            env=env,
            working_dir=self.project_dir,
            dry=self.dry,
            executor_config=task_options.get("executor"),
            capture_stdout=task_options.get("capture_stdout", False),
        )

    def get_env_file(self, envfile_path_str: str) -> Dict[str, str]:
        if envfile_path_str in self._envfile_cache:
            return self._envfile_cache[envfile_path_str]

        result = {}

        envfile_path = self.project_dir.joinpath(envfile_path_str)
        if envfile_path.is_file():
            try:
                with envfile_path.open() as envfile:
                    result = load_env_file(envfile)
            except ValueError as error:
                message = error.args[0]
                raise ExecutionError(
                    f"Syntax error in referenced envfile: {envfile_path_str!r}; {message}"
                ) from error

        else:
            self.ui.print_msg(
                f"Warning: Poe failed to locate envfile at {envfile_path_str!r}",
                verbosity=1,
            )

        self._envfile_cache[envfile_path_str] = result
        return result
