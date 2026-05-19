from __future__ import annotations

import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, NamedTuple

from ..config.primitives import EmptyDict, EnvDefault, EnvfileOption
from ..exceptions import ConfigValidationError, PoeException
from ..executor.task_run import PoeTaskRun
from ..io import PoeIO
from ..options import PoeOptions

if TYPE_CHECKING:
    from ..config import ConfigPartition, PoeConfig
    from ..config.partition import GroupConfig
    from ..context import RunContext
    from ..env.task_env import TaskEnv
    from ..helpers.parse.core import AstNode
    from ..ui import PoeUi
    from .args import PoeTaskArgs


_TASK_NAME_PATTERN = re.compile(r"^[A-Za-z_][\w\-:+]*$")
"""
Pattern for valid task names: must start with an ASCII letter or
underscore, followed by any combination of word chars, hyphen, colon,
or plus. Used by both runtime validation and the schema generator's
tasks_map patternProperties.

Note: the previous pattern was Unicode-aware via `\\w` for the first
char, combined with a separate `.isalpha()` runtime check. The unified
form is ASCII-only — JSON Schema regex portability and de facto task
naming conventions make ASCII-only the correct choice here.
"""


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


TaskContent = str | Sequence[str | Mapping[str, Any]]
TaskDef = str | Mapping[str, Any] | Sequence[str | Mapping[str, Any]]


class TaskSpecFactory:
    __cache: dict[str, PoeTask.TaskSpec]
    config: PoeConfig

    def __init__(self, config: PoeConfig):
        self.__cache = {}
        self.config = config

    def __contains__(self, other) -> bool:
        return other in self.__cache

    def get(
        self,
        task_name: str,
        task_def: TaskDef | None = None,
        task_type: str | None = None,
        parent: PoeTask.TaskSpec | None = None,
    ) -> PoeTask.TaskSpec:
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
        source: ConfigPartition,
        parent: PoeTask.TaskSpec | None = None,
        group: GroupConfig | None = None,
    ) -> PoeTask.TaskSpec:
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
            group=group,
        )

    def load_all(self):
        for task_name in self.config.get_tasks().keys():
            self.load(task_name)

        return self

    def load(self, task_name: str):
        task = self.config.lookup_task(task_name)
        if task is None:
            raise PoeException(f"Cannot instantiate unknown task {task_name!r}")

        task_def = task.task_def

        task_type = PoeTask.resolve_task_type(task_def, self.config)
        if not task_type:
            raise ConfigValidationError(
                "Task definition must be a string, a list, or a table including exactly"
                " one task key\n"
                f"Available task keys: {set(PoeTask.get_task_types())!r}",
                task_name=task_name,
                filename=(
                    None if task.partition.is_primary else str(task.partition.path)
                ),
            )

        self.__cache[task_name] = self.create(
            task_name, task_type, task_def, source=task.partition, group=task.group
        )

    def __iter__(self):
        return iter(self.__cache.values())


class TaskContext(NamedTuple):
    """
    Collection of contextual config inherited from a parent task to a child task
    """

    config: PoeConfig
    cwd: str
    io: PoeIO
    ui: PoeUi
    specs: TaskSpecFactory

    @property
    def verbosity(self) -> int:
        return self.io.verbosity

    @classmethod
    def from_task(cls, parent_task: PoeTask, task_spec: PoeTask.TaskSpec):
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
        args: dict | list | None = None
        """
        Define CLI options, positional arguments, or flags that this task should
        accept.
        """

        capture_stdout: str | None = None
        """
        Redirects the task output to a file with the given path. Supports
        environment variable interpolation.
        """

        cwd: str | None = None
        """
        Specify the current working directory that this task should run with. This
        can be a relative path from the project root or an absolute path, and
        environment variables can be used in the format ${VAR_NAME}.
        """

        deps: Sequence[str] | None = None
        """
        A list of task invocations that will be executed before this one. Each item
        in the list is a reference to another task defined within the tasks object.
        """

        env: Mapping[str, str | EnvDefault] = EmptyDict
        """
        A map of environment variables to be set for this task.
        """

        envfile: str | Sequence[str] | EnvfileOption = ()
        """
        Provide one or more env files to be loaded before running this task. If an
        array is provided, files will be loaded in the given order.
        """

        executor: Mapping[str, str | Sequence[str] | bool] | str | None = None
        """
        Configure the executor type for running tasks. Can be 'auto', 'poetry',
        'uv', 'virtualenv', or 'simple', with 'auto' being the default.
        """

        help: str | None = None
        """
        Help text to be displayed next to the task name in the documentation when
        poe is run without specifying a task.
        """

        uses: Mapping[str, str] | None = None
        """
        Allows this task to use the output of other tasks which are executed first.
        The values are references to the names of the tasks, and the keys are
        environment variables by which the results of those tasks will be
        accessible in this task.
        """

        verbosity: Literal[-2, -1, 0, 1, 2] | None = None
        """
        Specify the verbosity level for this task, from -2 (least verbose) to 2
        (most verbose), overriding the project level verbosity setting, which
        defaults to 0.
        """

        def validate(self):
            """
            Validation rules that don't require any extra context go here.
            """

        @classmethod
        def normalize(
            cls,
            source: Mapping[str, Any] | list[Mapping[str, Any]],
            strict: bool = True,
        ):
            """
            if executor is provided as just a string, then expand it to a dict with type
            """

            for item in super().normalize(source, strict):
                item = dict(item)

                # Normalize executor option:
                # > Mapping[str, str | Sequence[str] | bool] | str | None
                #     => Mapping[str, str | Sequence[str | bool] | bool]
                if isinstance((executor := item.get("executor")), str):
                    item["executor"] = {"type": executor}

                yield item

    class TaskSpec:
        name: str
        content: TaskContent
        options: PoeTask.TaskOptions
        task_type: type[PoeTask]
        source: ConfigPartition
        parent: PoeTask.TaskSpec | None = None
        group: GroupConfig | None = None

        def __init__(
            self,
            name: str,
            task_def: dict[str, Any],
            factory: TaskSpecFactory,
            source: ConfigPartition,
            *,
            parent: PoeTask.TaskSpec | None = None,
            group: GroupConfig | None = None,
        ):
            self.name = name
            self.content = task_def[self.task_type.__key__]
            self.options = self._parse_options(task_def)
            self.source = source
            self.parent = parent
            self.group = group

        def _parse_options(self, task_def: dict[str, Any]) -> PoeTask.TaskOptions:
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
            parent_env: TaskEnv,
            io: PoeIO,
            uses_values: Mapping[str, str] | None = None,
        ) -> TaskEnv:
            """
            Resolve the TaskEnv for this task, relative to the given parent_env
            """

            result = parent_env.clone(io=io)

            # Include env vars from outputs of upstream dependencies
            if uses_values:
                result.update(uses_values)

            result.set("POE_CONF_DIR", str(self.source.config_dir))
            result.apply_env_config(
                envfile_option=self.options.get("envfile"),
                config_env=self.options.get("env"),
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

        def get_args(self, io: PoeIO) -> PoeTaskArgs | None:
            if self.options.args:
                from .args import PoeTaskArgs

                return PoeTaskArgs(self.options.args, self.name, io=io)
            return None

        def create_task(
            self,
            invocation: tuple[str, ...],
            ctx: TaskContext,
            capture_stdout: str | bool = False,
        ) -> PoeTask:
            return self.task_type(
                spec=self,
                invocation=invocation,
                capture_stdout=capture_stdout,
                ctx=ctx,
            )

        def validate(self, config: PoeConfig, task_specs: TaskSpecFactory):
            try:
                self._base_validations(config, task_specs)
                self._task_validations(config, task_specs)
            except ConfigValidationError as error:
                error.task_name = self.name
                raise

        def _base_validations(self, config: PoeConfig, task_specs: TaskSpecFactory):
            """
            Perform validations on this TaskSpec that apply to all task types
            """
            if not self.parent and not _TASK_NAME_PATTERN.match(self.name):
                raise ConfigValidationError(
                    "Task names must start with a letter or underscore and contain "
                    "only alphanumeric characters, colon, underscore, dash, or plus."
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

        def _task_validations(self, config: PoeConfig, task_specs: TaskSpecFactory):
            """
            Perform validations on this TaskSpec that apply to a specific task type
            """

    spec: TaskSpec
    ctx: TaskContext
    _parsed_args: tuple[dict[str, str], tuple[str, ...]] | None = None
    _parsed_content: AstNode | None = None

    __task_types: ClassVar[dict[str, type[PoeTask]]] = {}
    __upstream_invocations: (
        dict[str, list[tuple[str, ...]] | dict[str, tuple[str, ...]]] | None
    ) = None

    def __init__(
        self,
        spec: TaskSpec,
        invocation: tuple[str, ...],
        ctx: TaskContext,
        capture_stdout: str | bool = False,
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
        config: PoeConfig,
        array_item: bool | str = False,
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

    def _parse_content(self) -> AstNode | None:
        """
        Parse and cache task content as an AST node for structured inspection.

        Returns None by default. Subclasses with structured content (cmd, ref)
        override this to return a parsed tree, enabling precise detection of
        $POE_EXTRA_ARGS references that excludes comments and superset variable names.
        """
        return None

    def _content_uses_extra_args(self) -> bool:
        """
        Check if task content explicitly references $POE_EXTRA_ARGS.

        If the content includes a reference to $POE_EXTRA_ARGS that means that the
        task content is already designed to include extra arguments, and that we
        should not append extra arguments automatically to the end of the content.
        """
        if (tree := self._parse_content()) is not None:
            from ..helpers.parse.command import ParamExpansion
            from ..helpers.parse.core import SyntaxNode

            stack: list[AstNode] = [tree]
            while stack:
                node = stack.pop()
                if isinstance(node, ParamExpansion):
                    if node.param_name == "POE_EXTRA_ARGS":
                        return True
                    if node.operation:
                        stack.append(node.operation.argument)
                elif isinstance(node, SyntaxNode):
                    stack.extend(node)
            return False

        content = self.spec.content
        return "$POE_EXTRA_ARGS" in content or "${POE_EXTRA_ARGS" in content

    def get_parsed_arguments(
        self, env: TaskEnv
    ) -> tuple[dict[str, Any], tuple[str, ...]]:
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
                    extra_args = ()

                self._parsed_args = (
                    task_args.parse(option_args, env, self.ctx.ui.program_name),
                    extra_args,
                )

            else:
                self._parsed_args = ({}, all_args)

        return self._parsed_args

    async def run(
        self,
        context: RunContext,
        parent_env: TaskEnv | None = None,
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
        self, context: RunContext, env: TaskEnv, task_state: PoeTaskRun
    ):
        """
        This method must be implemented by a subclass and is expected to mutate the
        supplied task_state.
        """
        raise NotImplementedError

    def _get_executor(
        self,
        context: RunContext,
        env: TaskEnv,
        *,
        resolve_python: bool = False,
        delegate_dry_run: bool = False,
    ):
        executor = context.get_executor(
            self.invocation,
            env,
            working_dir=self.get_working_dir(env),
            executor_config=self.spec.options.get("executor"),
            group_executor_config=(
                self.spec.group.executor if self.spec.group else None
            ),
            capture_stdout=self.capture_stdout,
            resolve_python=resolve_python,
            delegate_dry_run=delegate_dry_run,
            io=self.ctx.io,
        )
        # Make POE_ACTIVE variable available for interpolating into task content
        if executor.__key__:
            env.set("POE_ACTIVE", executor.__key__)
        return executor

    def get_working_dir(
        self,
        env: TaskEnv,
    ) -> Path:
        cwd_option = env.fill_template(self.spec.options.get("cwd", self.ctx.cwd))
        working_dir = Path(cwd_option)

        if not working_dir.is_absolute():
            working_dir = self.ctx.config.project_dir.joinpath(working_dir).resolve()

        return working_dir

    def iter_upstream_tasks(self, context: RunContext) -> Iterator[tuple[str, PoeTask]]:
        invocations = self._get_upstream_invocations(context)
        for invocation in invocations["deps"]:
            yield ("", self._instantiate_dep(invocation, capture_stdout=False))
        for key, invocation in invocations["uses"].items():
            yield (key, self._instantiate_dep(invocation, capture_stdout=True))

    def _get_upstream_invocations(self, context: RunContext):
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
            parsed_args, extra_args = self.get_parsed_arguments(env)
            env.register_task_args(parsed_args, extra_args)

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
    ) -> PoeTask:
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

    @classmethod
    def __schema_fragment__(cls, ctx: Any) -> dict:
        """
        Emit the JSON Schema fragment for this task variant.

        Composes `cls.TaskOptions.__schema_fragment__(ctx)` (which gives
        the options-dict shape) with the discriminator key (`cls.__key__`)
        typed by `cls.__content_type__`, and marks the discriminator as
        required.

        Subclasses with irregular content shape override this and call
        `super().__schema_fragment__(ctx)` to get the base assembly,
        then refine specific parts.
        """
        from poethepoet.options.annotations import TypeAnnotation
        from poethepoet.schema.translate import translate_type

        fragment = cls.TaskOptions.__schema_fragment__(ctx)

        # The discriminator key (e.g. "cmd", "shell") with the right
        # content type. We translate __content_type__ as a primitive
        # annotation so str → string, list → array.
        content_annotation = TypeAnnotation.parse(cls.__content_type__)
        content_schema = translate_type(content_annotation, ctx)

        fragment["properties"][cls.__key__] = content_schema
        # Append the discriminator to required (sorted, no duplicates).
        required = set(fragment.get("required", []))
        required.add(cls.__key__)
        fragment["required"] = sorted(required)

        return fragment

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
