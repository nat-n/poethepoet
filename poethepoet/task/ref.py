from typing import TYPE_CHECKING

from ..exceptions import ConfigValidationError
from ..executor.task_run import PoeTaskRun
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

    async def _handle_run(
        self, context: "RunContext", env: "EnvVarsManager", task_state: PoeTaskRun
    ):
        """
        Lookup and delegate to the referenced task
        """
        import shlex

        named_arg_values, extra_args = self.get_parsed_arguments(env)
        env.update(named_arg_values)

        ref_invocation = (
            *(
                env.fill_template(token)
                for token in shlex.split(env.fill_template(self.spec.content.strip()))
            ),
            *extra_args,
        )

        task_spec = self.ctx.specs.get(ref_invocation[0])
        task = task_spec.create_task(
            invocation=ref_invocation, ctx=TaskContext.from_task(self, task_spec)
        )

        if task.has_deps():
            await self._run_task_graph(task, context, env, task_state)
            await task_state.finalize()
            return

        child_task = await task.run(context=context, parent_env=env)
        await task_state.add_child(child_task)
        await task_state.finalize()
        await child_task.wait(suppress_errors=False)

    async def _run_task_graph(
        self,
        task: "PoeTask",
        context: "RunContext",
        env: "EnvVarsManager",
        task_state: PoeTaskRun,
    ):
        from ..exceptions import ExecutionError
        from .graph import TaskExecutionGraph

        graph = TaskExecutionGraph(task, context)
        plan = graph.get_execution_plan()
        for stage in plan:
            for stage_task in stage:
                if stage_task == task:
                    # The final sink task gets special treatment
                    return await task_state.add_child(
                        await task.run(context=context, parent_env=env)
                    )

                dep_task = await stage_task.run(context=context)
                await task_state.add_child(dep_task)
                await dep_task.wait()
                if dep_task.has_failure:
                    raise ExecutionError(
                        f"Task graph aborted after failed task {stage_task.name!r}"
                    )
        # This should not be possible to reach
        raise ExecutionError("Task graph did not contain the expected sink task")
