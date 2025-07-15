from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from os import environ
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Optional, Union

from ..exceptions import ConfigValidationError, ExecutionError, PoeException
from .base import PoeTask, TaskContext

if TYPE_CHECKING:
    from ..config import ConfigPartition, PoeConfig
    from ..context import RunContext
    from ..env.manager import EnvVarsManager
    from .base import TaskSpecFactory


POE_DEBUG = environ.get("POE_DEBUG", "0") == "1"


class ParallelTask(PoeTask):
    """
    A task consisting of multiple tasks that run in parallel
    """

    content: list[Union[str, dict[str, Any]]]

    __key__ = "parallel"
    __content_type__: ClassVar[type] = list

    class TaskOptions(PoeTask.TaskOptions):
        ignore_fail: Literal[True, False, "return_zero", "return_non_zero"] = False
        default_item_type: Optional[str] = None

        def validate(self):
            """
            Validation rules that don't require any extra context go here.
            """
            super().validate()
            if self.default_item_type is not None and not PoeTask.is_task_type(
                self.default_item_type, content_type=str
            ):
                raise ConfigValidationError(
                    "Unsupported value for option `default_item_type`,\n"
                    f"Expected one of {PoeTask.get_task_types(content_type=str)}"
                )
            if self.capture_stdout is not None:
                raise ConfigValidationError(
                    "Unsupported option for parallel task `capture_stdout`"
                )

    class TaskSpec(PoeTask.TaskSpec):
        content: list
        options: "ParallelTask.TaskOptions"
        subtasks: Sequence[PoeTask.TaskSpec]

        def __init__(
            self,
            name: str,
            task_def: dict[str, Any],
            factory: "TaskSpecFactory",
            source: "ConfigPartition",
            parent: Optional["PoeTask.TaskSpec"] = None,
        ):
            super().__init__(name, task_def, factory, source, parent)

            self.subtasks = []
            for index, sub_task_def in enumerate(task_def[ParallelTask.__key__]):
                if not isinstance(sub_task_def, (str, dict, list)):
                    raise ConfigValidationError(
                        f"Item #{index} in parallel task should be a value of "
                        "type: str | dict | list",
                        task_name=self.name,
                    )

                subtask_name = (
                    sub_task_def
                    if (
                        isinstance(sub_task_def, str)
                        and (sub_task_def[0].isalpha() or sub_task_def[0] == "_")
                    )
                    else ParallelTask._subtask_name(name, index)
                )
                task_type_key = self.task_type.resolve_task_type(
                    sub_task_def,
                    factory.config,
                    array_item=task_def.get("default_item_type", True),
                )

                try:
                    self.subtasks.append(
                        factory.get(
                            subtask_name, sub_task_def, task_type_key, parent=self
                        )
                    )
                except PoeException:
                    raise ConfigValidationError(
                        f"Failed to interpret subtask #{index} in parallel",
                        task_name=self.name,
                    )

        def _task_validations(self, config: "PoeConfig", task_specs: "TaskSpecFactory"):
            """
            Perform validations on this TaskSpec that apply to a specific task type
            """
            for subtask in self.subtasks:
                if subtask.args:
                    raise ConfigValidationError(
                        "Unsupported option 'args' for task declared inside parallel"
                    )

                subtask.validate(config, task_specs)

    spec: TaskSpec

    def __init__(
        self,
        spec: TaskSpec,
        invocation: tuple[str, ...],
        ctx: TaskContext,
        capture_stdout: bool = False,
    ):
        assert capture_stdout in (False, None)
        super().__init__(spec, invocation, ctx)
        self.subtasks = [
            task_spec.create_task(
                invocation=(self._subtask_name(task_spec.name, index),),
                ctx=TaskContext.from_task(self),
            )
            for index, task_spec in enumerate(spec.subtasks)
        ]

    def _handle_run(
        self,
        context: "RunContext",
        env: "EnvVarsManager",
    ) -> int:
        named_arg_values, extra_args = self.get_parsed_arguments(env)
        env.update(named_arg_values)

        if not named_arg_values and any(arg.strip() for arg in self.invocation[1:]):
            raise PoeException(f"Parallel task {self.name!r} does not accept arguments")

        if len(self.subtasks) > 1:
            # Indicate on the global context that there are multiple stages
            context.multistage = True

        ignore_fail = self.spec.options.ignore_fail

        non_zero_subtasks = self._run_subtasks(context, env, ignore_fail)

        # Handle any failed subtasks
        if non_zero_subtasks and ignore_fail == "return_non_zero":
            plural = "s" if len(non_zero_subtasks) > 1 else ""
            raise ExecutionError(
                f"Subtask{plural} {', '.join(repr(st) for st in non_zero_subtasks)} "
                "returned non-zero exit status"
            )
        return 0

    def _run_subtasks(
        self,
        context: "RunContext",
        env: "EnvVarsManager",
        ignore_fail: Union[Literal["return_zero", "return_non_zero"], bool],
    ):
        non_zero_subtasks: list[str] = []
        subtask_futures: dict[PoeTask, Future] = {}
        with ThreadPoolExecutor() as executor:
            for subtask in self.subtasks:
                task_result = None

                if POE_DEBUG:
                    print(f" . Starting subtask {subtask.name!r}")

                subtask_futures[subtask] = executor.submit(
                    self._run_subtask,
                    subtask=subtask,
                    context=context,
                    env=env,
                    ignore_fail=ignore_fail,
                )

            all_done = False
            while not all_done:  # Wait for all subtasks to complete
                all_done = True

                # Wait one second for the first task in each loop run,
                # then check the others for results
                # This avoids 100% CPU usage by polling task results
                # all the time and exits early if any subtask failed.
                first_subtask = True

                for subtask, future in subtask_futures.items():
                    if not first_subtask and not future.done():
                        all_done = False
                        continue
                    first_subtask = False

                    try:
                        task_result = future.result(timeout=1)
                    except TimeoutError:
                        all_done = False
                        continue

                    if POE_DEBUG:
                        print(
                            f" . Subtask {subtask.name!r} finished with {task_result}"
                        )

                    if task_result:
                        if not ignore_fail:
                            executor.shutdown(wait=False, cancel_futures=True)
                            raise ExecutionError(
                                "Parallel task run aborted after failed subtask "
                                + f"{subtask.name!r}"
                            )
                        non_zero_subtasks.append(subtask.name)

        return non_zero_subtasks

    @staticmethod
    def _run_subtask(
        subtask: "PoeTask",
        context: "RunContext",
        env: "EnvVarsManager",
        ignore_fail: Union[Literal["return_zero", "return_non_zero"], bool],
    ) -> int:
        try:
            task_result = subtask.run(context=context, parent_env=env)
        except ExecutionError as error:
            if ignore_fail:
                print("Warning:", error.msg)
                return 0
            else:
                print("Error:", error.msg)
                return -1

        return task_result

    @classmethod
    def _subtask_name(cls, task_name: str, index: int):
        return f"{task_name}[{index}]"
