import re
import shlex
from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, Tuple

from ..exceptions import ConfigValidationError, ExpressionParseError
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
            from ..helpers.python import parse_and_validate

            try:
                target_module, target_ref = self.content.split(":", 1)
                if not target_ref.isidentifier():
                    parse_and_validate(target_ref, call_only=True)
            except (ValueError, ExpressionParseError):
                raise ConfigValidationError(
                    f"Invalid callable reference {self.content!r}\n"
                    "(expected something like `module:callable` or `module:callable()`)"
                )

    spec: TaskSpec

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: "EnvVarsManager",
    ) -> int:
        from ..helpers.python import format_class

        named_arg_values = self.get_named_arg_values(env)
        env.update(named_arg_values)

        target_module, function_call = self.parse_content(named_arg_values)
        function_ref = function_call[: function_call.index("(")]

        argv = [
            self.name,
            *(env.fill_template(token) for token in extra_args),
        ]

        # TODO: check whether the project really does use src layout, and don't do
        #       sys.path.append('src') if it doesn't

        script = [
            "import asyncio,os,sys;",
            "from inspect import iscoroutinefunction as _c;",
            "from os import environ;",
            "from importlib import import_module as _i;",
            f"sys.argv = {argv!r}; sys.path.append('src');",
            f"{format_class(named_arg_values)}",
            f"_m = _i('{target_module}');",
            f"_r = asyncio.run(_m.{function_call}) if _c(_m.{function_ref})",
            f" else _m.{function_call};",
        ]

        if self.spec.options.get("print_result"):
            script.append("_r is not None and print(_r);")

        # Exactly which python executable to use is usually resolved by the executor
        # It's important that the script contains no line breaks to avoid issues on
        # windows
        cmd = ("python", "-c", "".join(script))

        self._print_action(shlex.join(argv), context.dry)
        return self._get_executor(context, env).execute(
            cmd, use_exec=self.spec.options.get("use_exec", False)
        )

    def parse_content(self, args: Optional[Dict[str, Any]]) -> Tuple[str, str]:
        """
        Returns the module to load, and the function call to execute.

        Will raise an exception if the function call contains invalid syntax or
        references variables that are not in scope.
        """

        from ..helpers.python import resolve_expression

        try:
            target_module, target_ref = self.spec.content.strip().split(":", 1)
        except ValueError:
            raise ExpressionParseError(
                f"Invalid task content: {self.spec.content.strip()!r}"
            )

        if target_ref.isidentifier():
            if args:
                return target_module, f"{target_ref}(**({args}))"
            return target_module, f"{target_ref}()"

        function_call = resolve_expression(
            target_ref,
            set(args or tuple()),
            call_only=True,
            allowed_vars={"sys", "os", "environ"},
        )
        # Strip out any new lines because they can be problematic on windows
        function_call = re.sub(r"((\r\n|\r|\n) | (\r\n|\r|\n))", " ", function_call)
        function_call = re.sub(r"(\r\n|\r|\n)", " ", function_call)

        return target_module, function_call
