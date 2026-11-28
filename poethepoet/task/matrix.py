from __future__ import annotations

import inspect
import re
from collections.abc import Mapping
from itertools import product
from typing import TYPE_CHECKING, Any, ClassVar

from ..exceptions import ConfigValidationError, ExecutionError
from ..helpers import is_valid_env_var
from .base import PoeTask, TaskContext

if TYPE_CHECKING:
    from ..config import ConfigPartition, PoeConfig
    from ..config.partition import GroupConfig
    from ..context import RunContext
    from ..env.task_env import TaskEnv
    from ..executor.task_run import PoeTaskRun
    from ..options.annotations import Disinherited
    from .base import TaskSpecFactory


SUBTASK_OPTIONS_BLOCKLIST = ("args", "deps", "uses", "uses_env")

# Matrix values are embedded in the names of the tasks generated for each
# combination, which are resolved from the CLI and referenced from other tasks,
# so they are restricted to characters that are safe in a task name. Dot
# separated groups are allowed so that values such as python versions work.
_VALUE_PATTERN = re.compile(r"[\w:+-]+(?:\.[\w:+-]+)*")

_SCALAR_TYPES = (str, int, float, bool)


class MatrixTask(PoeTask):
    """
    Runs a subtask once for each combination of matrix variable values, with each
    variable exposed to the subtask as an environment variable.

    A matrix task is an orchestration task: the task option provides an inline
    definition that is called once per combination, and each combination also
    gets a generated task name such as test-py3.11 so that a single combination
    can be run on its own.
    """

    __key__ = "matrix"
    __content_type__: ClassVar[type] = dict

    class TaskOptions(PoeTask.TaskOptions):
        task: str | dict
        """
        An inline definition for the task to run for each combination of matrix
        variable values. The matrix variables are available to the task as
        environment variables, e.g. as ${py} in the task content or executor
        config.
        """

        # A matrix task runs its subtask once per combination, so it has no single
        # output to capture; disinherit the option so it is rejected during config
        # parsing and omitted from the schema.
        capture_stdout: Disinherited[str | None] = None

    class TaskSpec(PoeTask.TaskSpec):
        content: Mapping[str, list]
        options: MatrixTask.TaskOptions
        dimensions: tuple[str, ...]
        values: tuple[tuple[str, ...], ...]
        combinations: tuple[tuple[str, ...], ...]
        subtasks: tuple[PoeTask.TaskSpec, ...]

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
            super().__init__(
                name, task_def, factory, source, parent=parent, group=group
            )

            # Non-mapping content is reported by validation
            matrix: Mapping[str, Any] = (
                self.content if isinstance(self.content, Mapping) else {}
            )
            if isinstance(self.content, Mapping) and not matrix:
                raise ConfigValidationError(
                    "Option 'matrix' must declare at least one matrix variable",
                    task_name=self.name,
                )

            dimensions: list[str] = []
            value_lists: list[tuple[str, ...]] = []
            for dimension, values in matrix.items():
                if not is_valid_env_var(dimension):
                    raise ConfigValidationError(
                        f"Invalid matrix variable name {dimension!r}: matrix "
                        "variable names must be valid environment variable names",
                        task_name=self.name,
                    )
                if not isinstance(values, list) or not values:
                    raise ConfigValidationError(
                        f"Matrix variable {dimension!r} must be declared with a "
                        "non-empty list of values",
                        task_name=self.name,
                    )

                value_strings: list[str] = []
                for value in values:
                    if not isinstance(value, _SCALAR_TYPES):
                        raise ConfigValidationError(
                            f"Invalid value {value!r} for matrix variable "
                            f"{dimension!r}: values must be strings, numbers, or "
                            "booleans",
                            task_name=self.name,
                        )
                    value_string = str(value)
                    if not _VALUE_PATTERN.fullmatch(value_string):
                        raise ConfigValidationError(
                            f"Invalid value {value!r} for matrix variable "
                            f"{dimension!r}: values must be non-empty and may only "
                            "contain word characters, colon, plus, dash, or dot "
                            "separated groups",
                            task_name=self.name,
                        )
                    value_strings.append(value_string)

                if len(set(value_strings)) != len(value_strings):
                    raise ConfigValidationError(
                        f"Matrix variable {dimension!r} declares duplicate values",
                        task_name=self.name,
                    )

                dimensions.append(dimension)
                value_lists.append(tuple(value_strings))

            self.dimensions = tuple(dimensions)
            self.values = tuple(value_lists)
            self.combinations = tuple(product(*self.values))

            if not self.combinations:
                # Non-mapping content is reported by validation
                self.subtasks = ()
                return

            task_type = PoeTask.resolve_task_type(self.options.task, factory.config)
            if task_type is None:
                raise ConfigValidationError(
                    "Cannot determine the task type for the 'task' option of "
                    "matrix task",
                    task_name=self.name,
                )

            task_option = self.options.task
            base_def: dict[str, Any] = (
                {task_type: task_option}
                if isinstance(task_option, str)
                else dict(task_option)
            )
            declared_env = base_def.get("env")

            subtasks: list[PoeTask.TaskSpec] = []
            for combination in self.combinations:
                matrix_env = dict(zip(self.dimensions, combination, strict=True))
                subtask_def = {
                    **base_def,
                    "env": self._merge_env(matrix_env, declared_env),
                }
                subtask_spec = factory.get(
                    task_name=self._combination_name(combination),
                    task_def=subtask_def,
                    task_type=task_type,
                    parent=self,
                )
                factory.register_generated_task(subtask_spec, owner_name=self.name)
                subtasks.append(subtask_spec)

            self.subtasks = tuple(subtasks)

        @staticmethod
        def _merge_env(matrix_env: dict[str, str], declared_env: Any) -> Any:
            """
            Layer the matrix variables under the subtask's own env option, so that
            its values can reference the matrix variables, and an invalid env
            declaration is left in place for task option validation to report.
            """
            if declared_env is None:
                return matrix_env
            if isinstance(declared_env, Mapping):
                return {**matrix_env, **declared_env}
            return declared_env

        def _combination_name(self, combination: tuple[str, ...]) -> str:
            """
            The name of the task generated for a combination, e.g. test-py3.11,
            which can be used to run just that combination.
            """
            return "-".join(
                (
                    self.name,
                    *(
                        f"{dimension}{value}"
                        for dimension, value in zip(
                            self.dimensions, combination, strict=True
                        )
                    ),
                )
            )

        def _task_validations(self, config: PoeConfig, task_specs: TaskSpecFactory):
            """
            Perform validations on this TaskSpec that apply to a specific task type
            """
            if self.options.args:
                from .args import ArgSpec

                for arg_spec in ArgSpec.parse(self.options.args):
                    if (
                        arg_spec.name in self.dimensions
                        and arg_spec.get("default") is not None
                    ):
                        raise ConfigValidationError(
                            f"Argument {arg_spec.name!r} shares its name with a "
                            "matrix variable and cannot declare a default value, "
                            "which would permanently narrow the matrix to a single "
                            "combination",
                            task_name=self.name,
                        )

            task_option = self.options.task
            declared_env = (
                task_option.get("env") if isinstance(task_option, dict) else None
            )
            if isinstance(declared_env, Mapping):
                for dimension in self.dimensions:
                    if dimension in declared_env:
                        raise ConfigValidationError(
                            f"Matrix variable {dimension!r} cannot also be declared "
                            "in the 'task' option's env",
                            task_name=self.name,
                        )

            for subtask in self.subtasks:
                for banned_option in SUBTASK_OPTIONS_BLOCKLIST:
                    if subtask.options.get(banned_option, None) is not None:
                        raise ConfigValidationError(
                            f"Unsupported option {banned_option!r} for task "
                            "declared as the 'task' option of a matrix task"
                        )

                subtask.validate(config, task_specs)

    @classmethod
    def __schema_fragment__(cls, ctx: Any) -> dict:
        """
        Override: type the matrix content as a mapping of variables to arrays of
        values, and reference the recursive task_def union for the task option
        with subtask-level options forbidden per SUBTASK_OPTIONS_BLOCKLIST.
        ``capture_stdout`` is excluded by the Disinherited marker on
        ``TaskOptions``, so no manual drop is needed.
        """
        from ..options.annotations import TypeAnnotation
        from ..schema.translate import translate_type

        fragment = super().__schema_fragment__(ctx)

        content_schema = translate_type(TypeAnnotation.parse(Mapping[str, list]), ctx)
        if docstring := inspect.cleandoc(cls.__doc__ or ""):
            content_schema["description"] = docstring
        fragment["properties"][cls.__key__] = content_schema

        task_description = fragment["properties"]["task"].get("description")
        task_schema: dict[str, Any] = {
            "allOf": [
                {"$ref": "#/definitions/task_def"},
                *(
                    {
                        "if": {"type": "object", "additionalProperties": True},
                        "then": {
                            "type": "object",
                            "properties": {option: False},
                            "additionalProperties": True,
                        },
                    }
                    for option in SUBTASK_OPTIONS_BLOCKLIST
                ),
            ],
        }
        if task_description:
            task_schema["description"] = task_description
        fragment["properties"]["task"] = task_schema

        return fragment

    spec: TaskSpec
    _subtasks: tuple[PoeTask, ...]

    def __init__(
        self,
        spec: TaskSpec,
        invocation: tuple[str, ...],
        ctx: TaskContext,
        capture_stdout: bool = False,
    ):
        assert capture_stdout in (False, None)
        super().__init__(spec, invocation, ctx)
        self._subtasks = tuple(
            subtask_spec.create_task(
                invocation=(subtask_spec.name,),
                ctx=TaskContext.from_task(self, subtask_spec),
            )
            for subtask_spec in spec.subtasks
        )

    def _select_combinations(self, parsed_args: Mapping[str, Any]) -> list[int]:
        """
        Select the combinations to run. A dimension whose variable is already set
        by one of this task's args narrows the matrix to those values, so that a
        subset of the matrix can be selected without referring to the generated
        task names.
        """
        selected = list(range(len(self.spec.combinations)))

        for index, dimension in enumerate(self.spec.dimensions):
            value = parsed_args.get(dimension)
            if value is None or value is False or value == []:
                continue

            provided = (
                [str(item) for item in value]
                if isinstance(value, list)
                else [str(value)]
            )
            declared = self.spec.values[index]
            for item in provided:
                if item not in declared:
                    declared_list = ", ".join(repr(value) for value in declared)
                    raise ExecutionError(
                        f"Value {item!r} for matrix variable {dimension!r} is not "
                        f"one of the declared values: {declared_list}"
                    )

            selected = [
                combination_index
                for combination_index in selected
                if self.spec.combinations[combination_index][index] in provided
            ]

        return selected

    async def _handle_run(
        self, context: RunContext, env: TaskEnv, task_state: PoeTaskRun
    ):
        self._parse_and_register_args(env)
        parsed_args, _ = self.get_parsed_arguments(env)

        selected = self._select_combinations(parsed_args)

        if len(selected) > 1:
            # Indicate on the global context that there are multiple stages
            context.multistage = True

        for index in selected:
            subtask = self._subtasks[index]
            subtask_run: PoeTaskRun | None = None
            try:
                subtask_run = await subtask.run(context=context, parent_env=env)
                await task_state.add_child(subtask_run)
                await subtask_run.wait(suppress_errors=False)
            except ExecutionError as error:
                raise ExecutionError(
                    f"Matrix aborted after failed combination {subtask.name!r}"
                ) from error

            if not subtask_run or subtask_run.has_failure:
                raise ExecutionError(
                    f"Matrix aborted after failed combination {subtask.name!r}"
                )

        await task_state.finalize()
