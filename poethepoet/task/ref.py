from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, Any

from ..exceptions import ConfigValidationError, ExecutionError, PoeException
from .base import PoeTask, TaskContext

if TYPE_CHECKING:
    from typing import Annotated

    from ..config import PoeConfig
    from ..context import RunContext
    from ..env.task_env import TaskEnv
    from ..executor.task_run import PoeTaskRun
    from ..options.annotations import Metadata
    from .base import TaskSpecFactory


class RefTask(PoeTask):
    """
    Invokes another task by name, with or without arguments.
    """

    __key__ = "ref"

    class TaskOptions(PoeTask.TaskOptions):
        ignore_fail: bool = False
        """
        If true the failure of the referenced task will be ignored and the ref task
        will return exit code 0.
        """

        project: Annotated[str, Metadata(pattern=r"\S")] | None = None
        """
        Path to another poe project (a directory or a config file) in which to look up
        and run the referenced task, with that project's own config, env and executor.
        Relative to the project root unless absolute. Environment variables can be used
        in the format ${VAR_NAME}.
        """

        def validate(self):
            """
            Validation rules that don't require any extra context go here.
            """
            if self.executor:
                raise ConfigValidationError(
                    "Option 'executor' cannot be set on a ref task"
                )
            if self.project and self.cwd:
                raise ConfigValidationError(
                    "'project' and 'cwd' options"
                    " cannot be both provided on the same task."
                )

    @classmethod
    def __schema_fragment__(cls, ctx: Any) -> dict:
        """
        Override: ref tasks cannot declare an executor (see
        ``TaskOptions.validate``). Drop it from the inherited properties so
        the existing ``additionalProperties: false`` rejects the key at
        schema-validation time.
        """
        fragment = super().__schema_fragment__(ctx)
        fragment["properties"].pop("executor", None)
        fragment["if"] = {"required": ["project"]}
        # Encode the forbidden property as `{cwd: false}` rather than
        # `{not: {required: [cwd]}}`: semantically identical, but the later fails
        # ajv's strictRequired in schemastore
        fragment["then"] = {"properties": {"cwd": False}}
        return fragment

    class TaskSpec(PoeTask.TaskSpec):
        content: str
        options: RefTask.TaskOptions

        def _task_validations(self, config: PoeConfig, task_specs: TaskSpecFactory):
            """
            Perform validations on this TaskSpec that apply to a specific task type
            """

            if self.options.project:
                # The target lives in another project that is not loaded here, so
                # these checks are deferred to run time
                return

            task_name_ref = shlex.split(self.content)[0]

            if task_name_ref not in task_specs:
                raise ConfigValidationError(
                    f"Includes reference to unknown task {task_name_ref!r}"
                )

            ref_spec = task_specs.get(task_name_ref)
            if ref_spec.options.get("use_exec", False):
                raise ConfigValidationError(
                    f"Illegal reference to task with "
                    f"'use_exec' set to true: {task_name_ref!r}"
                )

            if self.options.capture_stdout and not self.accepts_option(
                "capture_stdout", task_specs
            ):
                raise ConfigValidationError(
                    "Option 'capture_stdout' cannot be set "
                    f"on a ref task referencing {ref_spec.task_type.__key__!r} task: "
                    f"{task_name_ref!r}"
                )

        def accepts_option(
            self,
            option_name: str,
            task_specs: TaskSpecFactory,
            _seen: set[int] | None = None,
        ) -> bool:
            """
            A ref forwards capture_stdout to its target at runtime, so it can be
            captured only if its target can. Other options use the default.
            """
            if option_name == "capture_stdout":
                if self.options.project:
                    # Target is in another project and unknown at load time
                    return True

                _seen = _seen or set()
                if id(self) in _seen:
                    # Part of a ref cycle; let graph-build cycle detection report it
                    return True
                _seen.add(id(self))

                target_name = shlex.split(self.content)[0]
                if target_name not in task_specs:
                    # Unknown target; let _task_validations report this error
                    return True
                return task_specs.get(target_name).accepts_option(
                    option_name, task_specs, _seen
                )
            return super().accepts_option(option_name, task_specs, _seen)

    spec: TaskSpec

    def _parse_content(self):
        if self._parsed_content is None:
            from ..helpers.parse import parse_template

            self._parsed_content = parse_template(self.spec.content.strip())
        return self._parsed_content

    async def _handle_run(
        self, context: RunContext, env: TaskEnv, task_state: PoeTaskRun
    ):
        """
        Lookup and delegate to the referenced task
        """

        ignore_fail = self.spec.options.ignore_fail
        if ignore_fail:
            task_state.ignore_failure(ignore_fail)

        extra_args = self._parse_and_register_args(env)

        expanded_content = env.fill_template(self._parse_content())
        invocation_tokens = tuple(
            env.fill_template(token) for token in shlex.split(expanded_content)
        )
        if self._content_uses_extra_args():
            ref_invocation = invocation_tokens
        else:
            ref_invocation = (*invocation_tokens, *extra_args)

        if self.spec.options.project:
            await self._run_in_project(
                self.spec.options.project, ref_invocation, context, env, task_state
            )
            return

        task_spec = self.ctx.specs.get(ref_invocation[0])
        task = task_spec.create_task(
            invocation=ref_invocation,
            ctx=TaskContext.from_task(self, task_spec),
            capture_stdout=self.capture_stdout,
        )

        if task.has_deps():
            try:
                await self._run_task_graph(task, context, env, task_state)
            except ExecutionError as error:
                if ignore_fail:
                    self._warn_subtask_failure(context, error.msg)
                else:
                    raise
            await task_state.finalize()
            return

        child_task = await task.run(context=context, parent_env=env)
        await task_state.add_child(child_task)
        await task_state.finalize()
        try:
            await child_task.wait(suppress_errors=False)
            self._adopt_target_output(context, task)
        except ExecutionError as error:
            if ignore_fail:
                self._warn_subtask_failure(context, error.msg)
            else:
                raise

    async def _run_in_project(
        self,
        project: str,
        ref_invocation: tuple[str, ...],
        context: RunContext,
        env: TaskEnv,
        task_state: PoeTaskRun,
    ):
        """
        Run the referenced task in the project given by the project option, with that
        project's own config, env and executor, in a child of the given context.
        """
        from .project_ref import (
            build_target_context,
            fill_project_option,
            resolve_project_path,
            run_target,
        )

        target_name = ref_invocation[0] if ref_invocation else ""
        project_display = project
        start_failure: Exception | None = None

        def stacked_error(error: Exception) -> ExecutionError:
            """
            Stack the given failure of the target under a headline naming this task and
            the target's project.
            """
            target_display = repr(target_name) if target_name else "its referenced task"
            return ExecutionError(
                f"Task {self.name!r} could not run {target_display}"
                f" in project {project_display}",
                error,
            )

        def start_error(error: Exception) -> Exception:
            """
            Stack the given failure to start the target, and record it so that
            ignore_fail can't swallow it.
            """
            nonlocal start_failure
            start_failure = stacked_error(error)
            return start_failure

        try:
            if not (filled_project := fill_project_option(project, env)).strip():
                # Resolving a blank path would silently run the task in this project
                raise ExecutionError("Project path is empty after templating")
            project_display = filled_project
            if not target_name:
                raise ExecutionError("Task reference is empty after templating")
            project_path = resolve_project_path(project_display, self.ctx.config)
            loaded_project = await context.get_loaded_project(project_path, self.ctx.io)
            child_context = context.for_project(
                loaded_project.config, env.get_subprocess_env_vars()
            )

            if target_name not in loaded_project.config.get_tasks():
                raise ExecutionError(f"Unrecognized task {target_name!r}")

            task_spec = loaded_project.specs.get(target_name)
            if task_spec.options.get("use_exec", False):
                raise ExecutionError(
                    "Illegal reference to task with "
                    f"'use_exec' set to true: {target_name!r}"
                )
            if (capture_stdout := self.capture_stdout) and isinstance(
                capture_stdout, str
            ):
                # The file path belongs to this ref, so fill it from this ref's env and
                # resolve it against this project, as for an in-project ref
                capture_stdout = str(
                    self.ctx.config.project_dir.joinpath(
                        env.fill_template(capture_stdout)
                    )
                )
            if capture_stdout and not task_spec.accepts_option(
                "capture_stdout", loaded_project.specs
            ):
                raise ExecutionError(
                    "Option 'capture_stdout' cannot be set "
                    f"on a ref task referencing {task_spec.task_type.__key__!r} task: "
                    f"{target_name!r}"
                )

            task = task_spec.create_task(
                invocation=ref_invocation,
                ctx=build_target_context(loaded_project, task_spec, self.ctx),
                capture_stdout=capture_stdout,
            )
        except (PoeException, ExecutionError) as error:
            raise start_error(error)

        try:
            await run_target(
                task,
                child_context,
                task_state,
                start_error=start_error,
                run_error=stacked_error,
            )
        except ExecutionError as error:
            # As for an in-project ref, ignore_fail covers failures of the target's
            # run (including poe errors stacked by run_error), but never a failure to
            # start it
            if error is start_failure or not self.spec.options.ignore_fail:
                raise
            self._warn_subtask_failure(context, error.msg)
        else:
            self._adopt_target_output(context, task, source_context=child_context)

        if task.has_deps():
            # As for the in-project graph path, finalize once the graph has run
            await task_state.finalize()

    def _adopt_target_output(
        self,
        context: RunContext,
        target: PoeTask,
        source_context: RunContext | None = None,
    ) -> None:
        """
        If this ref is being run as a uses/uses_env dependency, its output is expected
        under its own invocation but the target's executor saved it under the target's,
        in the source_context if the target ran in another project's context.
        """
        if self.capture_stdout is True:
            context.adopt_task_output(
                self.invocation, source_context or context, target.invocation
            )

    async def _run_task_graph(
        self,
        task: PoeTask,
        context: RunContext,
        env: TaskEnv,
        task_state: PoeTaskRun,
    ):
        from ..exceptions import ExecutionError
        from .graph import TaskExecutionGraph

        graph = TaskExecutionGraph(task, context, parent_env=env)
        plan = graph.get_execution_plan()
        for stage in plan:
            for stage_task in stage:
                if stage_task == task:
                    # The final sink task gets special treatment
                    sink_task_run = await task.run(context=context, parent_env=env)
                    await task_state.add_child(sink_task_run)
                    # Errors from child task runs are otherwise suppressed, so they
                    # must be raised here to fail this task
                    await sink_task_run.wait(suppress_errors=False)
                    self._adopt_target_output(context, task)
                    return

                dep_task = await stage_task.run(context=context)
                await task_state.add_child(dep_task)
                await dep_task.wait()
                if dep_task.has_failure:
                    raise ExecutionError(
                        f"Task graph aborted after failed task {stage_task.name!r}"
                    )
        # This should not be possible to reach
        raise ExecutionError("Task graph did not contain the expected sink task")
