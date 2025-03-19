from collections.abc import Iterator, Mapping, Sequence
from os import environ
from pathlib import Path
from typing import Any, Optional, Union

from ..exceptions import ConfigValidationError, ExpressionParseError, PoeException
from .file import PoeConfigFile
from .partition import ConfigPartition, IncludedConfig, PackagedConfig, ProjectConfig

POE_DEBUG = environ.get("POE_DEBUG", "0") == "1"


class PoeConfig:
    _project_config: ProjectConfig
    _included_config: list[IncludedConfig]
    _packaged_config: list[PackagedConfig]

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
    """
    A global cache of raw configs derived from task packages
    """
    _packaged_config_cache: dict[tuple[str, ...], dict] = {}

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
        self._packaged_config = []

    def lookup_task(
        self, name: str
    ) -> Union[tuple[Mapping[str, Any], ConfigPartition], tuple[None, None]]:
        task = self._project_config.get("tasks", {}).get(name, None)
        if task is not None:
            return task, self._project_config

        for include in reversed((*self._packaged_config, *self._included_config)):
            task = include.get("tasks", {}).get(name, None)
            if task is not None:
                return task, include

        return None, None

    def partitions(self, included_first=True) -> Iterator[ConfigPartition]:
        if included_first:
            yield from self._packaged_config
            yield from self._included_config
            yield self._project_config
        else:
            yield self._project_config
            yield from self._included_config
            yield from self._packaged_config

    @property
    def executor(self) -> Mapping[str, Any]:
        return self._project_config.options.executor

    @property
    def task_names(self) -> Iterator[str]:
        result = list(self._project_config.get("tasks", {}).keys())
        for config_part in self._included_config + self._packaged_config:
            for task_name in config_part.get("tasks", {}).keys():
                # Don't use a set to dedup because we want to preserve task order
                if task_name not in result:
                    result.append(task_name)
        yield from result

    @property
    def tasks(self) -> dict[str, Any]:
        result = dict(self._project_config.get("tasks", {}))
        for config_part in self._included_config + self._packaged_config:
            for task_name, task_def in config_part.get("tasks", {}).items():
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
        full_config = self._project_config.full_config
        return self._project_config.path.name == "pyproject.toml" and (
            "poetry" in full_config.get("tool", {})
            or (
                # Fallback required to work out of the box with some poetry 2.0 projects
                full_config.get("build-system", {}).get("build-backend", "")
                == "poetry.core.masonry.api"
            )
        )

    @property
    def is_uv_project(self) -> bool:
        # Note: That it can happen that a uv managed project has no uv config
        #       In this case, this check would fail.
        return (
            self._project_config.path.name == "pyproject.toml"
            and "uv" in self._project_config.full_config.get("tool", {})
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
            if target_path is not None:
                raise PoeException(
                    f"No poe configuration found from location {target_path}"
                )
            else:
                raise PoeException(
                    f"No poe configuration found from location {self._project_dir}"
                )

        self._load_includes(strict=strict)
        self._load_packages(strict=strict)

    def _load_packages(self, strict: bool = True):
        if not self._project_config.options.task_packages:
            return

        import json

        from ..helpers.script import parse_script_reference

        # Attempt to load tasks from each of the task_packages
        for script_reference in self._project_config.options.task_packages:
            try:
                # TODO: explicitly expose some env vars?

                target_module, function_call = parse_script_reference(script_reference)
            except ExpressionParseError:
                raise

            # TODO: print stuff for POE_DEBUG

            invocation = ("$task_package$", script_reference)

            if invocation not in self._packaged_config_cache:
                from ..context import InitializationContext
                from ..env.manager import EnvVarsManager

                context = InitializationContext(config=self)
                env = EnvVarsManager(self)  # TODO: craft an env
                executor = context.get_executor(
                    invocation=invocation,
                    env=env,
                    working_dir=self._project_dir,
                    capture_stdout=True,
                    resolve_python=True,
                )

                script = (
                    "import os,sys;"
                    "environ=os.environ;"
                    "from importlib import import_module as _i;"
                    f"sys.path.append('src');"
                    f"_m = _i('{target_module}');"
                    f"print(_m.{function_call.expression});"
                )
                try:
                    executor.execute(("python", "-c", script))
                except Exception:
                    raise

                try:
                    script_result = context.get_task_output(invocation)
                except Exception:
                    raise

                try:
                    self._packaged_config_cache[invocation] = json.loads(script_result)
                except Exception:
                    raise

            try:
                from importlib.util import find_spec

                spec = find_spec(target_module)
                if not spec or not spec.origin:
                    raise PoeException("TODO: write error message")

                self._packaged_config.append(
                    PackagedConfig(
                        full_config=self._packaged_config_cache[invocation],
                        path=Path(spec.origin),
                        project_dir=self._project_dir,
                        strict=strict,
                    )
                )
            except (PoeException, KeyError) as error:
                raise ConfigValidationError(
                    f"Invalid content in loaded config from {target_module}"
                ) from error

    def _load_includes(self, strict: bool = True):
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
                            self._project_dir.joinpath(include["cwd"]).resolve()
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
