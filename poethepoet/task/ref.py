from typing import TYPE_CHECKING, Sequence

from ..exceptions import ConfigValidationError
from .base import PoeTask, TaskContext

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext
    from ..env.manager import EnvVarsManager
    from .base import TaskSpecFactory


class RefTask(PoeTask):
    """
    A task consisting of a reference to another task
    """

    __key__ = "ref"

    class TaskOptions(PoeTask.TaskOptions):
        def validate(self):
            """
            Validation rules that don't require any extra context go here.
            """
            if self.executor:
                raise ConfigValidationError(
                    "Option 'executor' cannot be set on a ref task"
                )
            if self.capture_stdout:
                raise ConfigValidationError(
                    "Option 'capture_stdout' cannot be set on a ref task"
                )

    class TaskSpec(PoeTask.TaskSpec):
        content: str
        options: "RefTask.TaskOptions"

        def _task_validations(self, config: "PoeConfig", task_specs: "TaskSpecFactory"):
            """
            Perform validations on this TaskSpec that apply to a specific task type
            """

            import shlex

            task_name_ref = shlex.split(self.content)[0]

            if task_name_ref not in task_specs:
                raise ConfigValidationError(
                    f"Includes reference to unknown task {task_name_ref!r}"
                )

            if task_specs.get(task_name_ref).options.get("use_exec", False):
                raise ConfigValidationError(
                    f"Illegal reference to task with "
                    f"'use_exec' set to true: {task_name_ref!r}"
                )

    spec: TaskSpec

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: "EnvVarsManager",
    ) -> int:
        """
        Lookup and delegate to the referenced task
        """
        import shlex

        invocation = tuple(shlex.split(env.fill_template(self.spec.content.strip())))
        extra_args = [*invocation[1:], *extra_args]

        task = self.ctx.specs.get(invocation[0]).create_task(
            invocation=invocation, ctx=TaskContext.from_task(self)
        )

        if task.has_deps():
            return self._run_task_graph(task, context, extra_args, env)

        return task.run(context=context, extra_args=extra_args, parent_env=env)

    def _run_task_graph(
        self,
        task: "PoeTask",
        context: "RunContext",
        extra_args: Sequence[str],
        env: "EnvVarsManager",
    ) -> int:
        from ..exceptions import ExecutionError
        from .graph import TaskExecutionGraph

        graph = TaskExecutionGraph(task, context)
        plan = graph.get_execution_plan()
        for stage in plan:
            for stage_task in stage:
                if stage_task == task:
                    # The final sink task gets special treatment
                    return task.run(
                        context=context, extra_args=extra_args, parent_env=env
                    )

                task_result = stage_task.run(
                    context=context, extra_args=stage_task.invocation[1:]
                )
                if task_result:
                    raise ExecutionError(
                        f"Task graph aborted after failed task {stage_task.name!r}"
                    )
        return 0
