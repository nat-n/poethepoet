from pathlib import Path
from typing import (
    Dict,
    Mapping,
    Optional,
    Union,
    TYPE_CHECKING,
)
from .cache import EnvFileCache
from .template import apply_envvars_to_template

if TYPE_CHECKING:
    from .config import PoeConfig
    from .ui import PoeUi


class EnvVarsManager:
    _config: "PoeConfig"
    _ui: Optional["PoeUi"]
    _vars: Dict[str, str]
    envfiles: EnvFileCache

    def __init__(
        self,
        config: "PoeConfig",
        ui: Optional["PoeUi"],
        parent_env: Optional["EnvVarsManager"] = None,
        base_env: Optional[Mapping[str, str]] = None,
    ):
        self._config = config
        self._ui = ui
        self.envfiles = (
            # Reuse EnvFileCache from parent_env when possible
            EnvFileCache(Path(config.project_dir), self._ui)
            if parent_env is None
            else parent_env.envfiles
        )
        self._vars = {
            **(parent_env.to_dict() if parent_env is not None else {}),
            **(base_env or {}),
        }

        if parent_env is None:
            # Get env vars from envfile referenced in global options
            if self._config.global_envfile is not None:
                self._vars.update(self.envfiles.get(self._config.global_envfile))

            # Get env vars from global options
            self._apply_env_config(self._config.global_env)

        self._vars["POE_ROOT"] = str(self._config.project_dir)

    def _apply_env_config(
        self,
        config_env: Mapping[str, Union[str, Mapping[str, str]]],
    ):
        """
        Used for including env vars from global or task config.
        If a value is provided as a mapping from `"default"` to `str` then it is only
        used if the associated key doesn't already have a value.
        """
        for key, value in config_env.items():
            if isinstance(value, str):
                value_str = value
            elif key not in self._vars:
                value_str = value["default"]
            else:
                continue

            self._vars[key] = apply_envvars_to_template(
                value_str, self._vars, require_braces=True
            )

    def for_task(
        self, task_envfile: Optional[str], task_env: Optional[Mapping[str, str]]
    ) -> "EnvVarsManager":
        """
        Create a copy of self and extend it to include vars for the task.
        """
        result = EnvVarsManager(self._config, self._ui, parent_env=self)

        # Include env vars from envfile referenced in task options
        if task_envfile is not None:
            result.update(self.envfiles.get(task_envfile))

        # Include env vars from task options
        if task_env is not None:
            result._apply_env_config(task_env)

        return result

    def update(self, env_vars: Mapping[str, str]):
        self._vars.update(env_vars)
        return self

    def to_dict(self):
        return dict(self._vars)

    def fill_template(self, template: str):
        return apply_envvars_to_template(template, self._vars)
