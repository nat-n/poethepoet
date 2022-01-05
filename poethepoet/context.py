from pathlib import Path
from typing import (
    Any,
    Dict,
    Mapping,
    MutableMapping,
    Optional,
    Tuple,
    Union,
    TYPE_CHECKING,
)
from .exceptions import ExecutionError
from .executor import PoeExecutor
from .envfile import load_env_file

if TYPE_CHECKING:
    from .config import PoeConfig
    from .ui import PoeUi

# TODO: think about factoring env var concerns out to a dedicated class


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
        self.exec_cache = {}
        self.captured_stdout = {}
        self._envfile_cache = {}
        self.base_env = self.__build_base_env(env)

    def __build_base_env(self, env: Mapping[str, str]):
        # Get env vars from envfile referenced in global options
        result = dict(env)

        # Get env vars from envfile referenced in global options
        if self.config.global_envfile is not None:
            result.update(self.get_env_file(self.config.global_envfile))

        # Get env vars from global options
        self._update_env(result, self.config.global_env)

        result["POE_ROOT"] = str(self.config.project_dir)
        return result

    @staticmethod
    def _update_env(
        env: MutableMapping[str, str],
        extra_vars: Mapping[str, Union[str, Mapping[str, str]]],
    ):
        """
        Update the given env with the given extra_vars. If a value in extra_vars is
        indicated as `default` then only copy it over if that key is not already set on
        env.
        """
        for key, value in extra_vars.items():
            if isinstance(value, str):
                env[key] = value
            elif key not in env:
                env[key] = value["default"]

    @property
    def executor_type(self) -> Optional[str]:
        return self.config.executor["type"]

    def get_env(
        self,
        parent_env: Optional[Mapping[str, str]],
        task_envfile: Optional[str],
        task_env: Optional[Mapping[str, str]],
        task_uses: Optional[Mapping[str, Tuple[str, ...]]] = None,
    ) -> Dict[str, str]:
        result = dict(self.base_env, **(parent_env or {}))

        # Include env vars from envfile referenced in task options
        if task_envfile is not None:
            result.update(self.get_env_file(task_envfile))

        # Include env vars from task options
        if task_env is not None:
            self._update_env(result, task_env)

        # Include env vars from dependencies
        if task_uses is not None:
            result.update(self.get_dep_values(task_uses))

        return result

    def get_dep_values(
        self, used_task_invocations: Mapping[str, Tuple[str, ...]]
    ) -> Dict[str, str]:
        """
        Get env vars from upstream tasks declared via the uses option
        """
        return {
            var_name: self.captured_stdout[invocation]
            for var_name, invocation in used_task_invocations.items()
        }

    def get_executor(
        self,
        invocation: Tuple[str, ...],
        env: Mapping[str, str],
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
