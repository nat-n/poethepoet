from __future__ import annotations

import os
import shlex
from typing import TYPE_CHECKING, Any

from ..exceptions import ConfigValidationError
from ..helpers.script import parse_script_reference
from .base import PoeTask

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext
    from ..env.task_env import TaskEnv
    from ..executor.task_run import PoeTaskRun
    from .base import TaskSpecFactory


class ScriptTask(PoeTask):
    """
    Invokes a Python callable or module, optionally with values or expressions
    passed as arguments.
    """

    content: str

    __key__ = "script"

    class TaskOptions(PoeTask.TaskOptions):
        use_exec: bool = False
        """
        Specify that this task should be executed in the same process, instead of
        as a subprocess. Note: This feature has limitations, such as not being
        compatible with tasks that are referenced by other tasks and not working on
        Windows.
        """

        print_result: bool = False
        """
        If true then the return value of the Python callable will be output to
        stdout, unless it is None.
        """

        ignore_fail: bool | list[int] = False
        """
        Return exit code 0 even if the task fails, or specify a list of task exit
        codes to ignore.
        """

        def validate(self):
            super().validate()
            if self.use_exec and self.capture_stdout:
                raise ConfigValidationError(
                    "'use_exec' and 'capture_stdout'"
                    " options cannot be both provided on the same task."
                )

    class TaskSpec(PoeTask.TaskSpec):
        content: str
        options: ScriptTask.TaskOptions

        def _task_validations(self, config: PoeConfig, task_specs: TaskSpecFactory):
            """
            Perform validations on this TaskSpec that apply to a specific task type
            """

            from ..helpers.script import validate_script_or_module_reference

            validate_script_or_module_reference(self.content)

            if ":" not in self.content and self.options.get("print_result"):
                raise ConfigValidationError(
                    "'print_result' is not supported on a script task that "
                    "references a module (it only makes sense when the task "
                    "calls a python callable that returns a value)."
                )

    @classmethod
    def __schema_fragment__(cls, ctx: Any) -> dict:
        """
        Override: attach python-callable examples on the ``script``
        discriminator field, and encode two mutually-exclusive option
        combinations that the runtime also rejects:
        ``use_exec`` + ``capture_stdout`` (``TaskOptions.validate``);
        and ``print_result`` on a module-style script — recognised by the
        ``script`` reference containing no ``:`` (``_task_validations``).
        """
        fragment = super().__schema_fragment__(ctx)
        fragment["properties"]["script"]["examples"] = [
            "my_pkg.my_module",
            "my_pkg.my_module:main",
            "my_pkg.my_module:main(only='images', log_env={'LOG_PATH':'/var/log'})",
        ]
        fragment["allOf"] = [
            {
                "if": {
                    "properties": {"use_exec": {"const": True}},
                    "required": ["use_exec"],
                },
                "then": {"not": {"required": ["capture_stdout"]}},
            },
            {
                "if": {
                    "properties": {"script": {"pattern": "^[^:]*$"}},
                    "required": ["script"],
                },
                "then": {"not": {"required": ["print_result"]}},
            },
        ]
        return fragment

    spec: TaskSpec

    async def _handle_run(
        self, context: RunContext, env: TaskEnv, task_state: PoeTaskRun
    ):
        from ..helpers.python import format_class

        if ignore_fail := self.spec.options.ignore_fail:
            task_state.ignore_failure(ignore_fail)

        named_arg_values, extra_args = self.get_parsed_arguments(env)
        env.register_task_args(named_arg_values, extra_args)
        named_arg_values = env.get_args()

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
        self, context: RunContext, env: TaskEnv, task_state: PoeTaskRun
    ):
        """
        Execute the python module referenced by the task content
        """

        named_arg_values, extra_args = self.get_parsed_arguments(env)
        env.register_task_args(named_arg_values, extra_args)

        # Approximate the callable path's sys.path.append('src') by appending
        # '<project_root>/src' to PYTHONPATH. The absolute form means a task
        # with its own cwd (or invoking poe from a subdirectory) still resolves
        # to the project's src/, rather than the subprocess's cwd-relative src/.
        # All PYTHONPATH entries collectively precede site-packages in sys.path
        # regardless of internal order, so an installed package can still be
        # shadowed by a local src/ — fully mirroring append semantics would
        # require a wrapper script.
        # TODO: only do this when the project actually uses src layout
        #       (same caveat as the callable path).
        src_path = str(self.ctx.config.project_dir / "src")
        existing_pythonpath = env.get("PYTHONPATH", "")
        env.set(
            "PYTHONPATH",
            (
                f"{existing_pythonpath}{os.pathsep}{src_path}"
                if existing_pythonpath
                else src_path
            ),
        )

        argv = [
            *(
                task_args.format_argv(named_arg_values, env)
                if (task_args := self.task_args)
                else ()
            ),
            *extra_args,
        ]
        cmd = ("python", "-m", self.spec.content, *argv)

        action_summary = self.name + (f" {shlex.join(argv)}" if argv else "")
        self._print_action(action_summary, context.dry)

        executor = self._get_executor(context, env, resolve_python=True)
        process = await executor.execute(
            cmd, use_exec=self.spec.options.get("use_exec", False)
        )
        await task_state.add_process(process, finalize=True)
