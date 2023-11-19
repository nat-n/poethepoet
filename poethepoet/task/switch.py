from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    Literal,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

from ..exceptions import ConfigValidationError, ExecutionError, PoeException
from .base import PoeTask, TaskContext

if TYPE_CHECKING:
    from ..config import ConfigPartition, PoeConfig
    from ..context import RunContext
    from ..env.manager import EnvVarsManager
    from .base import TaskSpecFactory


DEFAULT_CASE = "__default__"
SUBTASK_OPTIONS_BLOCKLIST = ("args", "uses", "deps")


class SwitchTask(PoeTask):
    """
    A task that runs one of several `case` subtasks depending on the output of a
    `switch` subtask.
    """

    __key__ = "switch"
    __content_type__: ClassVar[Type] = list

    class TaskOptions(PoeTask.TaskOptions):
        control: Union[str, dict]
        default: Literal["pass", "fail"] = "fail"

        @classmethod
        def normalize(
            cls,
            config: Any,
            strict: bool = True,
        ):
            """
            Perform validations that require access to to the raw config.
            """
            if strict and isinstance(config, dict):
                # Subtasks may not declare certain options
                for subtask_def in config.get("switch", tuple()):
                    for banned_option in SUBTASK_OPTIONS_BLOCKLIST:
                        if banned_option in subtask_def:
                            if "case" not in subtask_def:
                                raise ConfigValidationError(
                                    "Default case includes incompatible option "
                                    f"{banned_option!r}"
                                )
                            raise ConfigValidationError(
                                f"Case {subtask_def.get('case')!r} includes "
                                f"incompatible option {banned_option!r}"
                            )

            return super().normalize(config, strict)

    class TaskSpec(PoeTask.TaskSpec):
        control_task_spec: PoeTask.TaskSpec
        case_task_specs: Tuple[Tuple[Tuple[Any, ...], PoeTask.TaskSpec], ...]
        options: "SwitchTask.TaskOptions"

        def __init__(
            self,
            name: str,
            task_def: Dict[str, Any],
            factory: "TaskSpecFactory",
            parent: Optional["PoeTask.TaskSpec"] = None,
            source: Optional["ConfigPartition"] = None,
        ):
            super().__init__(name, task_def, factory, parent, source)

            switch_args = task_def.get("args")
            control_task_def = task_def["control"]

            if switch_args:
                if isinstance(control_task_def, str):
                    control_task_def = {
                        factory.config.default_task_type: control_task_def
                    }
                control_task_def = dict(control_task_def, args=switch_args)

            self.control_task_spec = factory.get(
                task_name=f"{name}[__control__]", task_def=control_task_def, parent=self
            )

            case_task_specs = []
            for switch_item in task_def["switch"]:
                case_task_def = dict(switch_item, args=switch_args)
                case = case_task_def.pop("case", DEFAULT_CASE)
                case_tuple = tuple(case) if isinstance(case, list) else (case,)
                case_task_index = ",".join(str(value) for value in case_tuple)
                case_task_specs.append(
                    (
                        case_tuple,
                        factory.get(
                            task_name=f"{name}[{case_task_index}]",
                            task_def=case_task_def,
                            parent=self,
                        ),
                    )
                )

            self.case_task_specs = tuple(case_task_specs)

        def _task_validations(self, config: "PoeConfig", task_specs: "TaskSpecFactory"):
            from collections import defaultdict

            allowed_control_task_types = ("expr", "cmd", "script")
            if (
                self.control_task_spec.task_type.__key__
                not in allowed_control_task_types
            ):
                raise ConfigValidationError(
                    f"Control task must have a type that is one of "
                    f"{allowed_control_task_types!r}"
                )

            cases: MutableMapping[Any, int] = defaultdict(int)
            for case_keys, case_task_spec in self.case_task_specs:
                for case_key in case_keys:
                    cases[case_key] += 1

            # Ensure case keys don't overlap (and only one default case)
            for case, count in cases.items():
                if count > 1:
                    if case is DEFAULT_CASE:
                        raise ConfigValidationError(
                            "Switch array includes more than one default case"
                        )
                    raise ConfigValidationError(
                        f"Switch array includes more than one case for {case!r}"
                    )

            if self.options.default != "fail" and DEFAULT_CASE in cases:
                raise ConfigValidationError(
                    "switch tasks should not declare both a default case and the "
                    "'default' option"
                )

            # Validate subtask specs
            self.control_task_spec.validate(config, task_specs)
            for _, case_task_spec in self.case_task_specs:
                case_task_spec.validate(config, task_specs)

    spec: TaskSpec
    control_task: PoeTask
    switch_tasks: Dict[str, PoeTask]

    def __init__(
        self,
        spec: TaskSpec,
        invocation: Tuple[str, ...],
        ctx: TaskContext,
        capture_stdout: bool = False,
    ):
        super().__init__(spec, invocation, ctx, capture_stdout)

        control_task_name = f"{spec.name}[__control__]"
        control_invocation: Tuple[str, ...] = (control_task_name,)
        options = self.spec.options
        if options.get("args"):
            control_invocation = (*control_invocation, *invocation[1:])

        self.control_task = self.spec.control_task_spec.create_task(
            invocation=control_invocation,
            ctx=TaskContext.from_task(self),
            capture_stdout=True,
        )

        self.switch_tasks = {}
        for case_keys, case_spec in spec.case_task_specs:
            task_invocation: Tuple[str, ...] = (f"{spec.name}[{','.join(case_keys)}]",)
            if options.get("args"):
                task_invocation = (*task_invocation, *invocation[1:])

            case_task = case_spec.create_task(
                invocation=task_invocation,
                ctx=TaskContext.from_task(self),
                capture_stdout=self.capture_stdout,
            )
            for case_key in case_keys:
                self.switch_tasks[case_key] = case_task

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: "EnvVarsManager",
    ) -> int:
        named_arg_values = self.get_named_arg_values(env)
        env.update(named_arg_values)

        if not named_arg_values and any(arg.strip() for arg in extra_args):
            raise PoeException(f"Switch task {self.name!r} does not accept arguments")

        # Indicate on the global context that there are multiple stages to this task
        context.multistage = True

        task_result = self.control_task.run(
            context=context,
            extra_args=(extra_args if self.spec.options.get("args") else tuple()),
            parent_env=env,
        )
        if task_result:
            raise ExecutionError(
                f"Switch task {self.name!r} aborted after failed control task"
            )

        if context.dry:
            self._print_action(
                "unresolved case for switch task", dry=True, unresolved=True
            )
            return 0

        control_task_output = context.get_task_output(self.control_task.invocation)
        case_task = self.switch_tasks.get(
            control_task_output, self.switch_tasks.get(DEFAULT_CASE)
        )

        if case_task is None:
            if self.spec.options.default == "pass":
                return 0
            raise ExecutionError(
                f"Control value {control_task_output!r} did not match any cases in "
                f"switch task {self.name!r}."
            )

        result = case_task.run(context=context, extra_args=extra_args, parent_env=env)

        if self.capture_stdout is True:
            # The executor saved output for the case task, but we need it to be
            # registered for this switch task as well
            context.save_task_output(
                self.invocation, context.get_task_output(case_task.invocation).encode()
            )

        return result
