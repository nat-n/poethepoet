from __future__ import annotations

import os
from collections.abc import (
    Callable,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
)
from typing import TYPE_CHECKING, Any, TypeVar, overload

from ..io import PoeIO
from .template import apply_envvars_to_template

if TYPE_CHECKING:
    from pathlib import Path

    from ..config import PoeConfig
    from ..config.primitives import EnvDefault, EnvfileOption
    from .cache import EnvFileCache


_T = TypeVar("_T")
ArgPrimitive = str | bool | int | float
ArgVars = dict[str, ArgPrimitive | list[ArgPrimitive]]


class TaskEnv(Mapping[str, str]):
    _envfiles: EnvFileCache
    _env_vars: dict[str, str]
    _lazy_vars: dict[str, Callable[[], str]]
    _arg_vars: ArgVars
    _private_vars: set[str]

    def __init__(
        self,
        env: dict[str, str],
        args: ArgVars,
        envfiles: EnvFileCache,
        lazy_vars: dict[str, Callable[[], str]],
        private_vars: set[str],
    ):
        """
        TaskEnv instances should be created via the create class method or the
        clone instance method rather than direct instanciation
        """
        self._envfiles = envfiles
        self._env_vars = env
        self._lazy_vars = lazy_vars
        self._arg_vars = args
        self._private_vars = private_vars

    @classmethod
    def create(
        cls,
        config: PoeConfig,
        base_env: Mapping[str, str] | None = None,
        io: PoeIO | None = None,
        cwd: Path | str | None = None,
    ):
        """
        Create a base TaskEnv
        """

        from ..helpers.git import GitRepo
        from .cache import EnvFileCache

        base_env = dict(base_env or {})
        io = io or PoeIO.get_default_io()
        cwd = str(cwd or os.getcwd())
        git_repo = GitRepo(config.project_dir)

        base_env["POE_ROOT"] = str(config.project_dir)

        if "POE_CWD" not in base_env:
            base_env["POE_CWD"] = cwd
            base_env["POE_PWD"] = cwd

        if io:
            base_env["POE_VERBOSITY"] = str(io.verbosity)

        return TaskEnv(
            env=base_env,
            args={},
            envfiles=EnvFileCache(config.project_dir, io),
            lazy_vars={
                "POE_GIT_DIR": lambda: str(git_repo.path or ""),
                "POE_GIT_ROOT": lambda: str(git_repo.main_path or ""),
            },
            private_vars=set(),
        )

    def clone(self, io: PoeIO | None = None):
        """
        Create a new TaskEnv based on this one as a base for a sub-task
        """

        env = dict(self._env_vars)
        if io:
            env["POE_VERBOSITY"] = str(io.verbosity)

        return TaskEnv(
            env=env,
            args=dict(self._arg_vars),
            envfiles=self._envfiles,
            lazy_vars=dict(self._lazy_vars),
            private_vars=set(self._private_vars),
        )

    def __getitem__(self, key: str) -> str:
        if (value := self.get(key)) is not None:
            return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self._env_vars)

    def __len__(self):
        return len(self._env_vars)

    @overload
    def get(self, key: str, /) -> str | None: ...

    @overload
    def get(self, key: str, /, default: str) -> str: ...

    @overload
    def get(self, key: str, /, default: _T) -> str | _T: ...

    def get(self, key: str, /, default: Any = None) -> Any:
        """
        Get the string value for the requested variable
        """
        if key in self._env_vars:
            return self._env_vars[key]

        if key in self._lazy_vars:
            # Resolve and save requested lazy variable
            value = self._lazy_vars.pop(key)()
            self._env_vars[key] = value
            return value

        return default

    def to_dict(self) -> dict[str, str]:
        """
        Get all variables as string values
        """
        return dict(self._env_vars)

    def get_subprocess_env_vars(self) -> dict[str, str]:
        """
        Get all public variables as string values
        """
        return {
            key: value
            for key, value in self._env_vars.items()
            if key not in self._private_vars
        }

    def get_args(self) -> ArgVars:
        """
        Get own and inherited args
        """
        return dict(self._arg_vars)

    def fill_template(self, template: str) -> str:
        """
        Resolve the given string remplate with available variables
        """
        return apply_envvars_to_template(template, self)

    def set(self, key: str, value: str):
        """
        Set environment variables
        """
        if key.startswith("_") and not any(char.isupper() for char in key):
            self._private_vars.add(key)
        self._env_vars[key] = value

    def update(self, vals: dict[str, str]):
        """
        Set environment variables
        """
        for key, val in vals.items():
            if key.startswith("_") and not any(char.isupper() for char in key):
                self._private_vars.add(key)
            self._env_vars[key] = val

    def register_task_args(self, args: Mapping[str, Any]):
        """
        Track typed argument variables, and map to env vars.
        """
        for key, value in args.items():
            self._arg_vars[key] = value

            if value is None or value is False or value == []:
                # False or unset arg value maps to unset env var
                self._env_vars.pop(key, None)
            elif isinstance(value, list):
                self.set(key, " ".join(str(item) for item in value))
            else:
                self.set(key, str(value))

    def apply_env_config(
        self,
        envfile_option: str | Sequence[str] | EnvfileOption,
        config_env: Mapping[str, str | EnvDefault],
        config_dir: Path,
        config_working_dir: Path,
    ):
        """
        Used for including env vars from global or task config.
        If a value is provided as a mapping from `"default"` to `str` then it is only
        used if the associated key doesn't already have a value.
        """

        scoped_vars = self.clone()
        scoped_vars.set("POE_CONF_DIR", str(config_dir))

        if envfile_option:
            for envfile_path, is_optional in _iter_envfile_paths(envfile_option):
                resolved_envfile = config_working_dir.joinpath(
                    apply_envvars_to_template(
                        envfile_path, scoped_vars, require_braces=True
                    )
                )
                self.update(self._envfiles.get(resolved_envfile, optional=is_optional))

        scoped_vars = self.clone()
        scoped_vars.set("POE_CONF_DIR", str(config_dir))

        for key, value in (config_env or {}).items():
            if isinstance(value, str):
                value_str = value
            elif key not in scoped_vars:
                value_str = value["default"]
            else:
                continue

            # TODO: think about how to support lazy eval from args here
            resolved_value = apply_envvars_to_template(
                value_str, scoped_vars, require_braces=True
            )
            self.set(key, resolved_value)
            scoped_vars.set(key, resolved_value)


def _iter_envfile_paths(
    envfile_option: str | Sequence[str] | EnvfileOption, is_optional: bool = False
) -> Iterable[tuple[str, bool]]:
    """
    Yield (envfile_path, is_optional) tuples from whatever form of envfile_option is
    provided.
    """

    if isinstance(envfile_option, str):
        yield envfile_option, is_optional
    elif isinstance(envfile_option, list | tuple):
        for item in envfile_option:
            yield item, is_optional
    elif isinstance(envfile_option, dict):
        if (expected := envfile_option.get("expected")) is not None:
            yield from _iter_envfile_paths(expected, False)
        if (optional := envfile_option.get("optional")) is not None:
            yield from _iter_envfile_paths(optional, True)
