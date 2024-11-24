from collections.abc import Iterator, Mapping, Sequence
from os import environ
from pathlib import Path
from typing import Any, Optional, Union

from ..exceptions import ConfigValidationError, PoeException
from .file import PoeConfigFile
from .partition import ConfigPartition, IncludedConfig, ProjectConfig

POE_DEBUG = environ.get("POE_DEBUG", "0") == "1"


class PoeConfig:
    _project_config: ProjectConfig
    _included_config: list[IncludedConfig]

    """
    The filenames to look for when loading config
    """
    _config_filenames: tuple[str, ...] = (
        "pyproject.toml",
        "poe_tasks.toml",
        "poe_tasks.yaml",
        "poe_tasks.json",
    )
    """
    The parent directory of the project config file
    """
    _project_dir: Path
    """
    This can be overridden, for example to align with poetry
    """
    _baseline_verbosity: int = 0

    def __init__(
        self,
        cwd: Optional[Union[Path, str]] = None,
        table: Optional[Mapping[str, Any]] = None,
        config_name: Optional[Union[str, Sequence[str]]] = None,
    ):
        if config_name is not None:
            if isinstance(config_name, str):
                self._config_filenames = (config_name,)
            else:
                self._config_filenames = tuple(config_name)

        self._project_dir = Path().resolve() if cwd is None else Path(cwd)
        self._project_config = ProjectConfig(
            {"tool.poe": table or {}}, path=self._project_dir, strict=False
        )
        self._included_config = []

    def lookup_task(
        self, name: str
    ) -> Union[tuple[Mapping[str, Any], ConfigPartition], tuple[None, None]]:
        task = self._project_config.get("tasks", {}).get(name, None)
        if task is not None:
            return task, self._project_config

        for include in reversed(self._included_config):
            task = include.get("tasks", {}).get(name, None)
            if task is not None:
                return task, include

        return None, None

    def partitions(self, included_first=True) -> Iterator[ConfigPartition]:
        if not included_first:
            yield self._project_config
        yield from self._included_config
        if included_first:
            yield self._project_config

    @property
    def executor(self) -> Mapping[str, Any]:
        return self._project_config.options.executor

    @property
    def task_names(self) -> Iterator[str]:
        result = list(self._project_config.get("tasks", {}).keys())
        for config_part in self._included_config:
            for task_name in config_part.get("tasks", {}).keys():
                # Don't use a set to dedup because we want to preserve task order
                if task_name not in result:
                    result.append(task_name)
        yield from result

    @property
    def tasks(self) -> dict[str, Any]:
        result = dict(self._project_config.get("tasks", {}))
        for config in self._included_config:
            for task_name, task_def in config.get("tasks", {}).items():
                if task_name in result:
                    continue
                result[task_name] = task_def
        return result

    @property
    def default_task_type(self) -> str:
        return self._project_config.options.default_task_type

    @property
    def default_array_task_type(self) -> str:
        return self._project_config.options.default_array_task_type

    @property
    def default_array_item_task_type(self) -> str:
        return self._project_config.options.default_array_item_task_type

    @property
    def shell_interpreter(self) -> tuple[str, ...]:
        raw_value = self._project_config.options.shell_interpreter
        if isinstance(raw_value, list):
            return tuple(raw_value)
        return (raw_value,)

    @property
    def verbosity(self) -> int:
        return self._project_config.get("verbosity", self._baseline_verbosity)

    @property
    def is_poetry_project(self) -> bool:
        return (
            self._project_config.path.name == "pyproject.toml"
            and "poetry" in self._project_config.full_config.get("tool", {})
        )

    @property
    def project_dir(self) -> Path:
        return self._project_dir

    def load(self, target_path: Optional[Union[Path, str]] = None, strict: bool = True):
        """
        target_path is the path to a file or directory for loading config
        If strict is false then some errors in the config structure are tolerated
        """

        for config_file in PoeConfigFile.find_config_files(
            target_path=Path(target_path or self._project_dir),
            filenames=self._config_filenames,
            search_parent=not target_path,
        ):
            config_file.load()

            if config_file.error:
                raise config_file.error

            elif config_file.is_valid:
                self._project_dir = config_file.path.parent

                config_content = config_file.load()
                assert config_content

                try:
                    self._project_config = ProjectConfig(
                        config_content,
                        path=config_file.path,
                        project_dir=self._project_dir,
                        strict=strict,
                    )
                except ConfigValidationError:
                    # Try again to load Config with minimal validation so we can still
                    # display the task list alongside the error
                    self._project_config = ProjectConfig(
                        config_content,
                        path=config_file.path,
                        project_dir=self._project_dir,
                        strict=False,
                    )
                    raise

                break

        else:
            raise PoeException(
                f"No poe configuration found from location {target_path}"
            )

        self._load_includes(strict=strict)

    def _load_includes(self: "PoeConfig", strict: bool = True):
        # Attempt to load each of the included configs
        for include in self._project_config.options.include:
            include_path = self._resolve_include_path(include["path"])

            if not include_path.exists():
                # TODO: print warning in verbose mode, requires access to ui somehow
                #       Maybe there should be something like a WarningService?

                if POE_DEBUG:
                    print(f" ! Could not include file from invalid path {include_path}")
                continue

            try:
                config_file = PoeConfigFile(include_path)
                config_content = config_file.load()
                assert config_content

                self._included_config.append(
                    IncludedConfig(
                        config_content,
                        path=config_file.path,
                        project_dir=self._project_dir,
                        cwd=(
                            self.project_dir.joinpath(include["cwd"]).resolve()
                            if include.get("cwd")
                            else None
                        ),
                        strict=strict,
                    )
                )
                if POE_DEBUG:
                    print(f"  Included config from {include_path}")
            except (PoeException, KeyError) as error:
                raise ConfigValidationError(
                    f"Invalid content in included file from {include_path}",
                    filename=str(include_path),
                ) from error

    def _resolve_include_path(self, include_path: str):
        from ..env.template import apply_envvars_to_template

        available_vars = {"POE_ROOT": str(self._project_dir)}

        if "${POE_GIT_DIR}" in include_path:
            from ..helpers.git import GitRepo

            git_repo = GitRepo(self._project_dir)
            available_vars["POE_GIT_DIR"] = str(git_repo.path or "")

        if "${POE_GIT_ROOT}" in include_path:
            from ..helpers.git import GitRepo

            git_repo = GitRepo(self._project_dir)
            available_vars["POE_GIT_ROOT"] = str(git_repo.main_path or "")

        include_path = apply_envvars_to_template(
            include_path, available_vars, require_braces=True
        )

        return self._project_dir.joinpath(include_path).resolve()
