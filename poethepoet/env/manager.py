import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Union

from .template import apply_envvars_to_template

if TYPE_CHECKING:
    from .cache import EnvFileCache
    from .config import PoeConfig
    from .ui import PoeUi


class EnvVarsManager:
    _config: "PoeConfig"
    _ui: Optional["PoeUi"]
    _vars: Dict[str, str]
    envfiles: "EnvFileCache"

    def __init__(  # TODO: check if we still need all these args!
        self,
        config: "PoeConfig",
        ui: Optional["PoeUi"],
        parent_env: Optional["EnvVarsManager"] = None,
        base_env: Optional[Mapping[str, str]] = None,
        cwd: Optional[Union[Path, str]] = None,
    ):
        from .cache import EnvFileCache

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

        self._vars["POE_ROOT"] = str(self._config.project_dir)

        self.cwd = str(cwd or os.getcwd())
        if "POE_CWD" not in self._vars:
            self._vars["POE_CWD"] = self.cwd
            self._vars["POE_PWD"] = self.cwd  # Deprecated

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self._vars.get(key, default)

    def set(self, key: str, value: str):
        self._vars[key] = value

    def apply_env_config(
        self,
        envfile: Optional[Union[str, List[str]]],
        config_env: Optional[Mapping[str, Union[str, Mapping[str, str]]]],
        config_dir: Path,
        config_working_dir: Path,
    ):
        """
        Used for including env vars from global or task config.
        If a value is provided as a mapping from `"default"` to `str` then it is only
        used if the associated key doesn't already have a value.
        """

        vars_scope = dict(self._vars, POE_CONF_DIR=str(config_dir))
        if envfile:
            if isinstance(envfile, str):
                envfile = [envfile]
            for envfile_path in envfile:
                self.update(
                    self.envfiles.get(
                        config_working_dir.joinpath(
                            apply_envvars_to_template(
                                envfile_path, vars_scope, require_braces=True
                            )
                        )
                    )
                )

        vars_scope = dict(self._vars, POE_CONF_DIR=str(config_dir))
        for key, value in (config_env or {}).items():
            if isinstance(value, str):
                value_str = value
            elif key not in vars_scope:
                value_str = value["default"]
            else:
                continue

            self._vars[key] = apply_envvars_to_template(
                value_str, vars_scope, require_braces=True
            )

    def update(self, env_vars: Mapping[str, Any]):
        # ensure all values are strings
        str_vars: Dict[str, str] = {}
        for key, value in env_vars.items():
            if isinstance(value, list):
                str_vars[key] = " ".join(str(item) for item in value)
            elif value is not None:
                str_vars[key] = str(value)

        self._vars.update(str_vars)

        return self

    def clone(self):
        return EnvVarsManager(
            config=self._config,
            ui=self._ui,
            parent_env=self,
            cwd=self.cwd,
        )

    def to_dict(self):
        return dict(self._vars)

    def fill_template(self, template: str):
        return apply_envvars_to_template(template, self._vars)
