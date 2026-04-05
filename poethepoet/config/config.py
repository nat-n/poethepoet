from __future__ import annotations

from os import environ
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..exceptions import ConfigValidationError, ExpressionParseError, PoeException
from ..helpers.eventloop import run_async
from .file import PoeConfigFile
from .partition import (
    ConfigPartition,
    GroupConfig,
    IncludedConfig,
    PackagedConfig,
    ProjectConfig,
    TaskConfig,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from ..io import PoeIO


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
    A global cache of raw configs derived from task packages
    """
    _packaged_config_cache: dict[tuple[str, ...], dict] = {}
    _tasks: Mapping[str, TaskConfig] = {}

    def __init__(
        self,
        cwd: Path | str | None = None,
        table: Mapping[str, Any] | None = None,
        config_name: str | Sequence[str] | None = None,
        io: PoeIO | None = None,
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

        if io:
            self._io = io
        else:
            from ..io import PoeIO

            self._io = PoeIO.get_default_io()

    def get_tasks(self) -> Mapping[str, TaskConfig]:
        """
        Collect tasks from across configs and groups.
        Project config tasks appear first and take precedence over includes.
        Group config (heading, executor) comes from the highest-precedence
        partition that defines that group; tasks are merged across partitions.
        """
        if not self._tasks:
            result: dict[str, TaskConfig] = {}
            group_configs: dict[str, GroupConfig] = {}
            for partition in self.partitions(included_first=False):
                for group_name, group_def in partition.get("groups", {}).items():
                    if group_name not in group_configs:
                        group_configs[group_name] = GroupConfig(group_name, group_def)
                for task_name, task_config in partition.collect_tasks().items():
                    if task_name not in result:
                        if task_config.group:
                            task_config.group = group_configs[task_config.group.name]
                        result[task_name] = task_config
            self._tasks = result

        return self._tasks

    def lookup_task(self, name: str) -> TaskConfig | None:
        return self.get_tasks().get(name)

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
        """
        Yield task names without building TaskConfig objects — used for shell
        completion where we only need the names.
        """
        seen: set[str] = set()
        for partition in self.partitions(included_first=False):
            for task_name in partition.get("tasks", {}).keys():
                if task_name not in seen:
                    yield task_name
                    seen.add(task_name)
            for group_def in partition.get("groups", {}).values():
                for task_name in group_def.get("tasks", {}).keys():
                    if task_name not in seen:
                        yield task_name
                        seen.add(task_name)

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
        return self._project_config.get("verbosity", 0)

    @property
    def is_poetry_project(self) -> bool:
        full_config = self._project_config.full_config
        return self._project_config.path.name == "pyproject.toml" and (
            "poetry" in full_config.get("tool", {})
            # Fallbacks required to work out of the box with some poetry 2.0 projects
            or (
                full_config.get("build-system", {}).get("build-backend", "")
                == "poetry.core.masonry.api"
            )
            or self._project_config.path.parent.joinpath("poetry.lock").is_file()
        )

    @property
    def is_uv_project(self) -> bool:
        # Note: That it can happen that a uv managed project has no uv config
        #       In this case, this check would fail.
        return self._project_config.path.name == "pyproject.toml" and (
            "uv" in self._project_config.full_config.get("tool", {})
            or self._project_config.path.parent.joinpath("uv.lock").is_file()
        )

    @property
    def project_dir(self) -> Path:
        return self._project_dir

    def load_sync(self, target_path: Path | str | None = None, strict: bool = True):
        """
        Load the config from the given path or the current working directory.
        If strict is false then some errors in the config structure are tolerated.
        Safe to call from both sync and async contexts.
        """

        return run_async(self.load(target_path=target_path, strict=strict))

    async def load(self, target_path: Path | str | None = None, strict: bool = True):
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
                if not config_content:
                    raise ConfigValidationError(
                        f"Config file at {config_file.path} is empty or invalid",
                        filename=str(config_file.path),
                    ) from config_file.error

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

        await self._load_includes(strict=strict)
        await self._load_packages(strict=strict)

    async def _load_packages(self, strict: bool = True):
        if not self._project_config.options.include_script:
            return
        for include_script in self._project_config.options.include_script:
            await self._load_include_script(include_script, strict=strict)

    async def _load_include_script(self, include_script: dict, strict: bool = True):
        import json

        from ..helpers.script import parse_script_reference

        # Attempt to load tasks from the include_script
        try:
            target_module, function_call = parse_script_reference(
                include_script["script"], allowed_vars={"os", "sys", "environ"}
            )
        except ExpressionParseError as error:
            raise PoeException("Invalid configuration for include_script") from error

        invocation = ("$include_script$", include_script["script"])

        if invocation not in self._packaged_config_cache:
            from ..context import InitializationContext
            from ..env.task_env import TaskEnv
            from ..io import PoeIO

            context = InitializationContext(config=self)
            env = TaskEnv.create(config=self, base_env=environ)
            executor = context.get_executor(
                invocation=invocation,
                env=env,
                working_dir=self._project_dir,
                executor_config=include_script.get("executor"),
                capture_stdout=True,
                resolve_python=True,
                io=PoeIO(parent=self._io, verbosity_offset=-1),
            )

            script = (
                "import os,sys,json;"
                "environ=os.environ;"
                "from importlib import import_module as _i;"
                f"sys.path.append('src');"
                "_o=sys.stdout;sys.stdout=sys.stderr;"
                f"_m = _i('{target_module}');"
                "sys.stdout=_o;"
                f"print(json.dumps(_m.{function_call.expression}));"
            )
            try:
                if self._io:
                    self._io.print_debug(
                        f" . Executing script for include_script {script!r}"
                    )
                subproc = await executor.execute(("python", "-c", script))
                await subproc.wait()
            except Exception as error:
                self._handle_error(
                    "subprocess execution failed for configured include_script"
                    f" {include_script['script']!r}",
                    error,
                    strict=strict,
                )
                return

            if subproc.returncode != 0:
                self._handle_error(
                    "include_script subprocess returned non-zero for "
                    f" {include_script['script']!r}",
                    strict=strict,
                )
                return

            # TODO: get the actual output from the subprocess directly?
            script_result = context.get_task_output(invocation)

            try:
                parsed_result = json.loads(script_result)
                if isinstance(parsed_result, str):
                    parsed_result = json.loads(parsed_result)
                self._packaged_config_cache[invocation] = parsed_result
            except json.decoder.JSONDecodeError as error:
                self._handle_error(
                    "Return value from include_script script must be valid json",
                    error,
                    strict=strict,
                )
                return

        try:
            config_json = dict(self._packaged_config_cache[invocation])
            config_path = Path(
                config_json.pop("config_path", self._project_config.path)
            )
            if config_json.get("tool", {}).get("poe"):
                pass
            elif tool_poe := config_json.get("tool.poe"):
                config_json = {"tool": {"poe": tool_poe}}
            else:
                config_json = {"tool": {"poe": config_json}}

            if include_cwd := include_script.get("cwd"):
                config_cwd = self._project_dir.joinpath(include_cwd).resolve()
            else:
                config_cwd = None

            self._packaged_config.append(
                PackagedConfig(
                    full_config=config_json,
                    path=config_path,
                    project_dir=self._project_dir,
                    cwd=config_cwd,
                    strict=strict,
                )
            )
        except (PoeException, KeyError) as error:
            raise ConfigValidationError(
                f"Invalid content in loaded config from {target_module}"
            ) from error

    def _handle_error(
        self, msg: str, error: Exception | None = None, strict: bool = True
    ):
        if strict:
            if error:
                raise PoeException(msg) from error
            else:
                raise PoeException(msg)
        elif self._io:
            self._io.print_debug(f" ! {msg}")

    async def _load_includes(self, strict: bool = True):
        # Attempt to load each of the included configs
        for include in self._project_config.options.include:
            await self._load_included_config(include, strict=strict)

    async def _load_included_config(
        self,
        include: dict,
        strict: bool = True,
        ancestors: Sequence[Path] = (),
        source_config_dir: Path | None = None,
    ):
        include_path = self.resolve_git_path(
            include["path"], source_config_dir=source_config_dir
        )
        if include_path in ancestors:
            if self._io:
                self._io.print_warning(
                    f"Cyclic include detected for path {include_path}",
                    message_verbosity=1,
                )
            return

        if not include_path.exists():
            if self._io:
                self._io.print_warning(
                    f"Poe could not include file from invalid path {include_path}",
                    message_verbosity=0,
                )
            return

        try:
            config_file = PoeConfigFile(include_path)
            config_content = config_file.load()
            if not config_content:
                raise ConfigValidationError(
                    f"Included file at {include_path} is empty or invalid",
                    filename=str(include_path),
                ) from config_file.error

            included_config = IncludedConfig(
                config_content,
                path=config_file.path,
                project_dir=self._project_dir,
                cwd=(
                    self.resolve_git_path(
                        include["cwd"], source_config_dir=source_config_dir
                    )
                    if include.get("cwd")
                    else None
                ),
                strict=strict,
            )
            self._included_config.append(included_config)

            if self._io:
                self._io.print_debug(f"  Included config from {include_path}")

            if include.get("recursive", True) and (
                child_includes := included_config.get("include")
            ):
                # Recursively load any includes from the included config
                # Therefore includes are loaded depth-first
                for child_include in child_includes:
                    await self._load_included_config(
                        child_include,
                        strict=strict,
                        ancestors=(*ancestors, include_path),
                        source_config_dir=include_path.parent,
                    )

        except (PoeException, KeyError) as error:
            if isinstance(error, ConfigValidationError) and error.filename:
                raise error
            raise ConfigValidationError(
                f"Invalid content in included file from {include_path}",
                filename=str(include_path),
            ) from error

    def resolve_git_path(
        self, resource_path: str, source_config_dir: Path | None = None
    ):
        """
        Resolve a path within the project that may contain POE_ROOT, POE_GIT_DIR, or
        POE_GIT_ROOT variables. Relative paths are resolved against source_config_dir if
        provided, otherwise against the project directory.
        """

        from ..env.template import apply_envvars_to_template

        if source_config_dir is None:
            source_config_dir = self._project_dir

        available_vars = {"POE_ROOT": str(self._project_dir)}

        if "${POE_CONF_DIR}" in resource_path:
            available_vars["POE_CONF_DIR"] = str(source_config_dir)

        if "${POE_GIT_DIR}" in resource_path:
            from ..helpers.git import GitRepo

            git_repo = GitRepo(self._project_dir)
            available_vars["POE_GIT_DIR"] = str(git_repo.path or "")

        if "${POE_GIT_ROOT}" in resource_path:
            from ..helpers.git import GitRepo

            git_repo = GitRepo(self._project_dir)
            available_vars["POE_GIT_ROOT"] = str(git_repo.main_path or "")

        resource_path = apply_envvars_to_template(
            resource_path, available_vars, require_braces=True
        )

        return source_config_dir.joinpath(resource_path).resolve()
