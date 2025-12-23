import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, NamedTuple, Optional, Union

from ..config.primitives import EmptyDict, EnvDefault
from ..exceptions import ConfigValidationError, PoeException
from ..executor.task_run import PoeTaskRun
from ..io import PoeIO
from ..options import PoeOptions

if TYPE_CHECKING:
    from ..config import ConfigPartition, PoeConfig
    from ..context import RunContext
    from ..env.manager import EnvVarsManager
    from ..ui import PoeUi
    from .args import PoeTaskArgs


_TASK_NAME_PATTERN = re.compile(r"^\w[\w\d\-\_\+\:]*$")


class MetaPoeTask(type):
    """
    This metaclass makes all descendants of PoeTask (task types) register themselves on
    declaration and validates that they include the expected class attributes.
    """

    def __init__(cls, *args):
        super().__init__(*args)
        if cls.__name__ == "PoeTask":
            return

        assert isinstance(getattr(cls, "__key__", None), str)
        assert issubclass(getattr(cls, "TaskOptions", None), PoeOptions)
        PoeTask._PoeTask__task_types[cls.__key__] = cls

        # Give each TaskSpec a reference to its parent PoeTask
        if "TaskSpec" in cls.__dict__:
            cls.TaskSpec.task_type = cls


TaskContent = Union[str, Sequence[Union[str, Mapping[str, Any]]]]
TaskDef = Union[str, Mapping[str, Any], Sequence[Union[str, Mapping[str, Any]]]]


class TaskSpecFactory:
    __cache: dict[str, "PoeTask.TaskSpec"]
    config: "PoeConfig"

    def __init__(self, config: "PoeConfig"):
        self.__cache = {}
        self.config = config

    def __contains__(self, other) -> bool:
        return other in self.__cache

    def get(
        self,
        task_name: str,
        task_def: TaskDef | None = None,
        task_type: str | None = None,
        parent: Optional["PoeTask.TaskSpec"] = None,
    ) -> "PoeTask.TaskSpec":
        if task_def and parent:
            # This is probably a subtask and will be cached by the parent task_spec
            if not task_type:
                task_type = PoeTask.resolve_task_type(task_def, self.config)
                assert task_type
            return self.create(
                task_name, task_type, task_def, source=parent.source, parent=parent
            )

        if task_name not in self.__cache:
            self.load(task_name)

        return self.__cache[task_name]

    def create(
        self,
        task_name: str,
        task_type: str,
        task_def: TaskDef,
        source: "ConfigPartition",
        parent: Optional["PoeTask.TaskSpec"] = None,
    ) -> "PoeTask.TaskSpec":
        """
        A parent task should be provided when this task is defined inline within another
        task, for example as part of a sequence.
        """
        if not isinstance(task_def, dict):
            task_def = {task_type: task_def}

        task_spec_cls = PoeTask.lookup_task_spec_cls(task_type)
        return task_spec_cls(
            name=task_name,
            task_def=task_def,
            factory=self,
            source=source,
            parent=parent,
        )

    def load_all(self):
        for task_name in self.config.task_names:
            self.load(task_name)

        return self

    def load(self, task_name: str):
        task_def, config_partition = self.config.lookup_task(task_name)

        if task_def is None or config_partition is None:
            raise PoeException(f"Cannot instantiate unknown task {task_name!r}")

        task_type = PoeTask.resolve_task_type(task_def, self.config)
        if not task_type:
            raise ConfigValidationError(
                "Task definition must be a string, a list, or a table including exactly"
                " one task key\n"
                f"Available task keys: {set(PoeTask.get_task_types())!r}",
                task_name=task_name,
                filename=(
                    None if config_partition.is_primary else str(config_partition.path)
                ),
            )

        self.__cache[task_name] = self.create(
            task_name, task_type, task_def, source=config_partition
        )

    def __iter__(self):
        return iter(self.__cache.values())


class TaskContext(NamedTuple):
    """
    Collection of contextual config inherited from a parent task to a child task
    """

    config: "PoeConfig"
    cwd: str
    io: "PoeIO"
    ui: "PoeUi"
    specs: "TaskSpecFactory"

    @property
    def verbosity(self) -> int:
        return self.io.verbosity

    @classmethod
    def from_task(cls, parent_task: "PoeTask", task_spec: "PoeTask.TaskSpec"):
        return cls(
            config=parent_task.ctx.config,
            cwd=str(parent_task.spec.options.get("cwd", parent_task.ctx.cwd)),
            specs=parent_task.ctx.specs,
            io=PoeIO(
                parent=parent_task.ctx.io,
                baseline_verbosity=task_spec.options.get(
                    "verbosity", parent_task.ctx.io._baseline_verbosity
                ),
            ),
            ui=parent_task.ctx.ui,
        )


class PoeTask(metaclass=MetaPoeTask):
    __key__: ClassVar[str]
    __content_type__: ClassVar[type] = str

    class TaskOptions(PoeOptions):
        args: Union[dict, list] | None = None
        capture_stdout: str | None = None
        cwd: str | None = None
        deps: Sequence[str] | None = None
        # ruff: noqa: UP007
        env: Mapping[str, Union[str, EnvDefault]] = EmptyDict
        envfile: Union[str, Sequence[str]] = ()
        executor: Mapping[str, str | Sequence[str] | bool] | str | None = None
        help: str | None = None
        uses: Mapping[str, str] | None = None
        verbosity: Literal[-2, -1, 0, 1, 2] | None = None

        def validate(self):
            """
            Validation rules that don't require any extra context go here.
            """

        @classmethod
        def normalize(cls, config: Any, strict: bool = True):
            """
            if executor is provided as just a string, then expand it to a dict with type
            """

            for item in super().normalize(config, strict):
                if (executor := item.get("executor")) and isinstance(executor, str):
                    yield {**item, "executor": {"type": executor}}
                yield item

    class TaskSpec:
        name: str
        content: TaskContent
        options: "PoeTask.TaskOptions"
        task_type: type["PoeTask"]
        source: "ConfigPartition"
        parent: Optional["PoeTask.TaskSpec"] = None

        def __init__(
            self,
            name: str,
            task_def: dict[str, Any],
            factory: TaskSpecFactory,
            source: "ConfigPartition",
            *,
            parent: Optional["PoeTask.TaskSpec"] = None,
        ):
            self.name = name
            self.content = task_def[self.task_type.__key__]
            self.options = self._parse_options(task_def)
            self.source = source
            self.parent = parent

        def _parse_options(self, task_def: dict[str, Any]) -> "PoeTask.TaskOptions":
            try:
                return next(  # type: ignore[return-value]
                    self.task_type.TaskOptions.parse(
                        task_def, extra_keys=(self.task_type.__key__,)
                    )
                )
            except ConfigValidationError as error:
                error.task_name = self.name
                raise

        def get_task_env(
            self,
            parent_env: "EnvVarsManager",
            io: "PoeIO",
            uses_values: Mapping[str, str] | None = None,
        ) -> "EnvVarsManager":
            """
            Resolve the EnvVarsManager for this task, relative to the given parent_env
            """
            task_envfile = self.options.get("envfile")
            task_env = self.options.get("env")

            result = parent_env.clone(io=io)

            # Include env vars from outputs of upstream dependencies
            if uses_values:
                result.update(uses_values)

            result.set("POE_CONF_DIR", str(self.source.config_dir))
            result.apply_env_config(
                task_envfile,
                task_env,
                config_dir=self.source.config_dir,
                config_working_dir=self.source.cwd,
            )

            return result

        @property
        def has_args(self) -> bool:
            """
            Returns True if this task has arguments defined.
            """
            return self.options.args is not None

        def get_args(self, io: PoeIO) -> Optional["PoeTaskArgs"]:
            if self.options.args:
                from .args import PoeTaskArgs

                return PoeTaskArgs(self.options.args, self.name, io=io)
            return None

        def create_task(
            self,
            invocation: tuple[str, ...],
            ctx: TaskContext,
            capture_stdout: Union[str, bool] = False,
        ) -> "PoeTask":
            return self.task_type(
                spec=self,
                invocation=invocation,
                capture_stdout=capture_stdout,
                ctx=ctx,
            )

        def validate(self, config: "PoeConfig", task_specs: TaskSpecFactory):
            try:
                self._base_validations(config, task_specs)
                self._task_validations(config, task_specs)
            except ConfigValidationError as error:
                error.task_name = self.name
                raise

        def _base_validations(self, config: "PoeConfig", task_specs: TaskSpecFactory):
            """
            Perform validations on this TaskSpec that apply to all task types
            """
            if not (self.name[0].isalpha() or self.name[0] == "_"):
                raise ConfigValidationError(
                    "Task names must start with a letter or underscore."
                )

            if not self.parent and not _TASK_NAME_PATTERN.match(self.name):
                raise ConfigValidationError(
                    "Task names characters must be alphanumeric, colon, underscore or "
                    "dash."
                )

            if not isinstance(self.content, self.task_type.__content_type__):
                raise ConfigValidationError(
                    f"Content for {self.task_type.__name__} must be a "
                    f"{self.task_type.__content_type__.__name__}"
                )

            if self.options.deps:
                for dep in self.options.deps:
                    dep_task_name = dep.split(" ", 1)[0]
                    if dep_task_name not in task_specs:
                        raise ConfigValidationError(
                            "'deps' option includes reference to unknown task: "
                            f"{dep_task_name!r}"
                        )

                    if task_specs.get(dep_task_name).options.get("use_exec", False):
                        raise ConfigValidationError(
                            f"'deps' option includes reference to task with "
                            f"'use_exec' set to true: {dep_task_name!r}"
                        )

            if self.options.uses:
                from ..helpers import is_valid_env_var

                for key, dep in self.options.uses.items():
                    if not is_valid_env_var(key):
                        raise ConfigValidationError(
                            f"'uses' option includes invalid key: {key!r}"
                        )

                    dep_task_name = dep.split(" ", 1)[0]
                    if dep_task_name not in task_specs:
                        raise ConfigValidationError(
                            "'uses' options includes reference to unknown task: "
                            f"{dep_task_name!r}"
                        )

                    referenced_task = task_specs.get(dep_task_name)
                    if referenced_task.options.get("use_exec", False):
                        raise ConfigValidationError(
                            f"'uses' option references task with 'use_exec' set to "
                            f"true: {dep_task_name!r}"
                        )
                    if referenced_task.options.get("capture_stdout"):
                        raise ConfigValidationError(
                            f"'uses' option references task with 'capture_stdout' "
                            f"option set: {dep_task_name!r}"
                        )

            if self.options.args:
                from .args import ArgSpec

                for _ in ArgSpec.parse(self.options.args):
                    pass

        def _task_validations(self, config: "PoeConfig", task_specs: TaskSpecFactory):
            """
            Perform validations on this TaskSpec that apply to a specific task type
            """

    spec: TaskSpec
    ctx: TaskContext
    _parsed_args: tuple[dict[str, str], tuple[str, ...]] | None = None

    __task_types: ClassVar[dict[str, type["PoeTask"]]] = {}
    __upstream_invocations: (
        dict[str, Union[list[tuple[str, ...]], dict[str, tuple[str, ...]]]] | None
    ) = None

    def __init__(
        self,
        spec: TaskSpec,
        invocation: tuple[str, ...],
        ctx: TaskContext,
        capture_stdout: Union[str, bool] = False,
    ):
        self.spec = spec
        self.invocation = invocation
        self.ctx = ctx
        self.capture_stdout = spec.options.capture_stdout or capture_stdout
        self._is_windows = sys.platform == "win32"

    @property
    def name(self):
        return self.spec.name

    @classmethod
    def lookup_task_spec_cls(cls, task_key: str) -> type[TaskSpec]:
        return cls.__task_types[task_key].TaskSpec

    @classmethod
    def resolve_task_type(
        cls,
        task_def: TaskDef,
        config: "PoeConfig",
        array_item: Union[bool, str] = False,
    ) -> str | None:
        if isinstance(task_def, str):
            if array_item:
                return (
                    array_item
                    if isinstance(array_item, str)
                    else config.default_array_item_task_type
                )
            else:
                return config.default_task_type

        elif isinstance(task_def, dict):
            task_type_keys = set(task_def.keys()).intersection(cls.__task_types)
            if len(task_type_keys) == 1:
                return next(iter(task_type_keys))

        elif isinstance(task_def, list):
            return config.default_array_task_type

        return None

    def get_parsed_arguments(
        self, env: "EnvVarsManager"
    ) -> tuple[dict[str, str], tuple[str, ...]]:
        """
        Returns a dict of parsed arguments, and a list extra arguments.

        If no args are defined for the task then all arguments are "extra",
        otherwise its only arguments passed after a `--`.
        """

        if self._parsed_args is None:
            all_args = self.invocation[1:]

            if task_args := self.spec.get_args(self.ctx.io):
                try:
                    split_index = all_args.index("--")
                    option_args = all_args[:split_index]
                    extra_args = all_args[split_index + 1 :]
                except ValueError:
                    option_args = all_args
                    extra_args = tuple()

                self._parsed_args = (
                    task_args.parse(option_args, env, self.ctx.ui.program_name),
                    extra_args,
                )

            else:
                self._parsed_args = ({}, all_args)

        return self._parsed_args

    async def run(
        self,
        context: "RunContext",
        parent_env: Optional["EnvVarsManager"] = None,
    ) -> PoeTaskRun:
        """
        Run this task
        """

        if self.ctx.io.is_debug_enabled():
            task_type_key = self.__key__  # type: ignore[attr-defined]
            self.ctx.io.print_debug(f" * Running     {task_type_key}:{self.name}")
            self.ctx.io.print_debug(f" . Invocation  {self.invocation!r}")

        upstream_invocations = self._get_upstream_invocations(context)

        if context.dry and upstream_invocations.get("uses", {}):
            self._print_action(
                (
                    "unresolved dependency task results via uses option for task "
                    f"{self.name!r}"
                ),
                dry=True,
                unresolved=True,
            )
            return await PoeTaskRun(self.name).finalize()

        task_env = self.spec.get_task_env(
            parent_env or context.env,
            io=self.ctx.io,
            uses_values=context._get_dep_values(upstream_invocations["uses"]),
        )

        if self.ctx.io.is_debug_enabled():
            named_arg_values, extra_args = self.get_parsed_arguments(task_env)
            self.ctx.io.print_debug(f" . Parsed args {named_arg_values!r}")
            self.ctx.io.print_debug(f" . Extra args  {extra_args!r}")

        task_state = PoeTaskRun(self.name, partial(self._handle_run, context, task_env))
        context.register_async_task(task_state.asyncio_task)
        task_state.add_new_process_callback(context.register_subprocess)

        return task_state

    async def _handle_run(
        self, context: "RunContext", env: "EnvVarsManager", task_state: PoeTaskRun
    ):
        """
        This method must be implemented by a subclass and is expected to mutate the
        supplied task_state.
        """
        raise NotImplementedError

    def _get_executor(
        self,
        context: "RunContext",
        env: "EnvVarsManager",
        *,
        resolve_python: bool = False,
        delegate_dry_run: bool = False,
    ):
        return context.get_executor(
            self.invocation,
            env,
            working_dir=self.get_working_dir(env),
            executor_config=self.spec.options.get("executor"),
            capture_stdout=self.capture_stdout,
            resolve_python=resolve_python,
            delegate_dry_run=delegate_dry_run,
            io=self.ctx.io,
        )

    def get_working_dir(
        self,
        env: "EnvVarsManager",
    ) -> Path:
        cwd_option = env.fill_template(self.spec.options.get("cwd", self.ctx.cwd))
        working_dir = Path(cwd_option)

        if not working_dir.is_absolute():
            working_dir = self.ctx.config.project_dir.joinpath(working_dir).resolve()

        return working_dir

    def iter_upstream_tasks(
        self, context: "RunContext"
    ) -> Iterator[tuple[str, "PoeTask"]]:
        invocations = self._get_upstream_invocations(context)
        for invocation in invocations["deps"]:
            yield ("", self._instantiate_dep(invocation, capture_stdout=False))
        for key, invocation in invocations["uses"].items():
            yield (key, self._instantiate_dep(invocation, capture_stdout=True))

    def _get_upstream_invocations(self, context: "RunContext"):
        """
        NB. this memoization assumes the context (and contained env vars) will be the
        same in all instances for the lifetime of this object. Whilst this should be OK
        for all current use cases is it strictly speaking something that this object
        should not know enough to safely assume. So we probably want to revisit this.
        """
        import shlex

        options = self.spec.options

        if self.__upstream_invocations is None:
            env = self.spec.get_task_env(context.env, io=self.ctx.io)
            env.update(self.get_parsed_arguments(env)[0])

            self.__upstream_invocations = {
                "deps": [
                    tuple(shlex.split(env.fill_template(task_ref)))
                    for task_ref in options.get("deps", ())
                ],
                "uses": {
                    key: tuple(shlex.split(env.fill_template(task_ref)))
                    for key, task_ref in options.get("uses", {}).items()
                },
            }

        return self.__upstream_invocations

    def _instantiate_dep(
        self, invocation: tuple[str, ...], capture_stdout: bool
    ) -> "PoeTask":
        task_spec = self.ctx.specs.get(invocation[0])
        return task_spec.create_task(
            invocation=invocation,
            ctx=TaskContext(
                config=self.ctx.config,
                cwd=str(self.ctx.config.project_dir),
                specs=self.ctx.specs,
                io=PoeIO(
                    parent=self.ctx.io,
                    baseline_verbosity=task_spec.options.get(
                        "verbosity", self.ctx.io._baseline_verbosity
                    ),
                ),
                ui=self.ctx.ui,
            ),
            capture_stdout=capture_stdout,
        )

    def has_deps(self) -> bool:
        return bool(
            self.spec.options.get("deps", False) or self.spec.options.get("uses", False)
        )

    @classmethod
    def is_task_type(cls, task_def_key: str, content_type: type | None = None) -> bool:
        """
        Checks whether the given key identifies a known task type.
        Optionally also check whether the given content_type matches the type of content
        for this tasks type.
        """
        return task_def_key in cls.__task_types and (
            content_type is None
            or cls.__task_types[task_def_key].__content_type__ is content_type
        )

    @classmethod
    def get_task_types(cls, content_type: type | None = None) -> tuple[str, ...]:
        if content_type:
            return tuple(
                task_type
                for task_type, task_cls in cls.__task_types.items()
                if task_cls.__content_type__ is content_type
            )
        return tuple(task_type for task_type in cls.__task_types.keys())

    def _print_action(self, action: str, dry: bool, unresolved: bool = False):
        """
        Print the action taken by a task just before executing it.
        """
        min_verbosity = -1 if dry else 0
        arrow = "??" if unresolved else "<=" if self.capture_stdout else "=>"
        self.ctx.io.print_poe_action(arrow, action, message_verbosity=min_verbosity)

    def __repr__(self):
        return f"<{self.__class__.__name__}:{self.name} at {hex(id(self))}>"

    class Error(Exception):
        pass
