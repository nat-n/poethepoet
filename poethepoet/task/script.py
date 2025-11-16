import shlex
from typing import TYPE_CHECKING

from ..exceptions import ConfigValidationError
from ..executor.task_run import PoeTaskRun
from ..helpers.script import parse_script_reference
from .base import PoeTask

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext
    from ..env.manager import EnvVarsManager
    from .base import TaskSpecFactory


class ScriptTask(PoeTask):
    """
    A task consisting of a reference to a python script
    """

    content: str

    __key__ = "script"

    class TaskOptions(PoeTask.TaskOptions):
        use_exec: bool = False
        print_result: bool = False

        def validate(self):
            super().validate()
            if self.use_exec and self.capture_stdout:
                raise ConfigValidationError(
                    "'use_exec' and 'capture_stdout'"
                    " options cannot be both provided on the same task."
                )

    class TaskSpec(PoeTask.TaskSpec):
        content: str
        options: "ScriptTask.TaskOptions"

        def _task_validations(self, config: "PoeConfig", task_specs: "TaskSpecFactory"):
            """
            Perform validations on this TaskSpec that apply to a specific task type
            """

            from ..helpers.script import validate_script_or_module_reference

            validate_script_or_module_reference(self.content)

            if ":" not in self.content and self.has_args:
                raise ConfigValidationError(
                    "Script task referencing a module (instead of a function) cannot "
                    "declare arguments."
                )

    spec: TaskSpec

    async def _handle_run(
        self, context: "RunContext", env: "EnvVarsManager", task_state: PoeTaskRun
    ):
        from ..helpers.python import format_class

        named_arg_values, _ = self.get_parsed_arguments(env)
        env.update(named_arg_values)

        # TODO: do something about extra_args, like raise an error?

        if ":" not in self.spec.content:
            return await self._run_module(context, env, task_state)

        target_module, function_call = parse_script_reference(
            self.spec.content,
            named_arg_values,
            allowed_vars={"sys", "os", "environ", "_dry_run"},
        )
        function_ref = function_call.function_ref

        argv = [
            self.name,
            *(env.fill_template(token) for token in self.invocation[1:]),
        ]

        # TODO: check whether the project really does use src layout, and don't do
        #       sys.path.append('src') if it doesn't

        has_dry_run_ref = "_dry_run" in function_call.referenced_globals
        dry_run = self.ctx.ui["dry_run"]

        script = [
            "import asyncio,os,sys;",
            "from inspect import iscoroutinefunction as _c;",
            "from importlib import import_module as _i;",
            "environ = os.environ;",
            f"_dry_run = {'True' if dry_run else 'False'};" if has_dry_run_ref else "",
            f"sys.argv = {argv!r}; sys.path.append('src');",
            f"{format_class(named_arg_values)}",
            f"_m = _i('{target_module}');",
            f"_r = asyncio.run(_m.{function_call.expression}) if _c(_m.{function_ref})",
            f" else _m.{function_call.expression};",
        ]

        if self.spec.options.get("print_result"):
            script.append("_r is not None and print(_r);")

        # Exactly which python executable to use is usually resolved by the executor
        # It's important that the script contains no line breaks to avoid issues on
        # windows
        cmd = ("python", "-c", "".join(script))

        self._print_action(shlex.join(argv), context.dry)
        executor = self._get_executor(
            context, env, delegate_dry_run=has_dry_run_ref, resolve_python=True
        )
        process = await executor.execute(
            cmd, use_exec=self.spec.options.get("use_exec", False)
        )
        await task_state.add_process(process, finalize=True)

    async def _run_module(
        self, context: "RunContext", env: "EnvVarsManager", task_state: PoeTaskRun
    ):
        """
        Execute the python module referenced by the task content
        """

        argv = [
            *(env.fill_template(token) for token in self.invocation[1:]),
        ]
        cmd = ("python", "-m", self.spec.content, *argv)

        action_summary = self.name + (f" {shlex.join(argv)}" if argv else "")
        self._print_action(action_summary, context.dry)

        executor = self._get_executor(context, env, resolve_python=True)
        process = await executor.execute(
            cmd, use_exec=self.spec.options.get("use_exec", False)
        )
        await task_state.add_process(process, finalize=True)
