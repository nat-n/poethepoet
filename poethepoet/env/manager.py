from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from ..io import PoeIO
from .template import apply_envvars_to_template

if TYPE_CHECKING:
    from pathlib import Path

    from ..config import PoeConfig
    from .cache import EnvFileCache


class EnvVarsManager(Mapping):
    _config: PoeConfig
    _io: PoeIO
    _vars: dict[str, str]
    envfiles: EnvFileCache

    def __init__(
        self,
        config: PoeConfig,
        io: PoeIO | None = None,
        parent_env: EnvVarsManager | None = None,
        base_env: Mapping[str, str] | None = None,
        cwd: Path | str | None = None,
    ):
        from ..helpers.git import GitRepo
        from .cache import EnvFileCache

        self._config = config
        self._io = io or PoeIO.get_default_io()
        self.envfiles = (
            # Reuse EnvFileCache from parent_env when possible
            EnvFileCache(config.project_dir, self._io)
            if parent_env is None
            else parent_env.envfiles
        )
        self._vars = {
            **(parent_env.to_dict() if parent_env is not None else {}),
            **(base_env or {}),
        }

        self._vars["POE_ROOT"] = str(config.project_dir)

        self.cwd = str(cwd or os.getcwd())
        if "POE_CWD" not in self._vars:
            self._vars["POE_CWD"] = self.cwd
            self._vars["POE_PWD"] = self.cwd

        if self._io:
            self._vars["POE_VERBOSITY"] = str(self._io.verbosity)

        self._git_repo = GitRepo(config.project_dir)

    def __getitem__(self, key):
        return self._vars[key]

    def __iter__(self):
        return iter(self._vars)

    def __len__(self):
        return len(self._vars)

    def get(self, key: Any, /, default: Any = None) -> str | None:
        if key == "POE_GIT_DIR":
            # This is a special case environment variable that is only set if requested
            self._vars["POE_GIT_DIR"] = str(self._git_repo.path or "")

        if key == "POE_GIT_ROOT":
            # This is a special case environment variable that is only set if requested
            self._vars["POE_GIT_ROOT"] = str(self._git_repo.main_path or "")

        return self._vars.get(key, default)

    def set(self, key: str, value: str):
        self._vars[key] = value

    def apply_env_config(
        self,
        envfile: str | list[str] | None,
        config_env: Mapping[str, str | Mapping[str, str]] | None,
        config_dir: Path,
        config_working_dir: Path,
    ):
        """
        Used for including env vars from global or task config.
        If a value is provided as a mapping from `"default"` to `str` then it is only
        used if the associated key doesn't already have a value.
        """

        scoped_env = self.clone()
        scoped_env.set("POE_CONF_DIR", str(config_dir))

        if envfile:
            if isinstance(envfile, str):
                envfile = [envfile]
            for envfile_path in envfile:
                self.update(
                    self.envfiles.get(
                        config_working_dir.joinpath(
                            apply_envvars_to_template(
                                envfile_path, scoped_env, require_braces=True
                            )
                        )
                    )
                )

        scoped_env = self.clone()
        scoped_env.set("POE_CONF_DIR", str(config_dir))

        for key, value in (config_env or {}).items():
            if isinstance(value, str):
                value_str = value
            elif key not in scoped_env:
                value_str = value["default"]
            else:
                continue

            self._vars[key] = apply_envvars_to_template(
                value_str, scoped_env, require_braces=True
            )
            scoped_env.set(key, self._vars[key])

    def update(self, env_vars: Mapping[str, Any]):
        # ensure all values are strings
        str_vars: dict[str, str] = {}
        for key, value in env_vars.items():
            if isinstance(value, list):
                str_vars[key] = " ".join(str(item) for item in value)
            elif value is not None:
                str_vars[key] = str(value)

        self._vars.update(str_vars)

        return self

    def clone(self, io: PoeIO | None = None) -> EnvVarsManager:
        return EnvVarsManager(
            config=self._config,
            io=io or self._io,
            parent_env=self,
            cwd=self.cwd,
        )

    def to_dict(self):
        return dict(self._vars)

    def fill_template(self, template: str):
        return apply_envvars_to_template(template, self._vars)
