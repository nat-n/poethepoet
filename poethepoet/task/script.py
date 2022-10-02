import ast
import re
from typing import (
    Any,
    Dict,
    Optional,
    Sequence,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)
from .base import PoeTask
from ..exceptions import ScriptParseError
from ..env.manager import EnvVarsManager
from ..helpers.python import (
    resolve_function_call,
    parse_and_validate,
)

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext


class ScriptTask(PoeTask):
    """
    A task consisting of a reference to a python script
    """

    content: str
    _callnode: ast.Call

    __key__ = "script"
    __options__: Dict[str, Union[Type, Tuple[Type, ...]]] = {
        "use_exec": bool,
        "print_result": bool,
    }

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: EnvVarsManager,
    ) -> int:
        # TODO: check whether the project really does use src layout, and don't do
        #       sys.path.append('src') if it doesn't
        target_module, function_call = self.parse_script_content(self.named_args)
        argv = [
            self.name,
            *(env.fill_template(token) for token in extra_args),
        ]

        script = [
            "import sys; ",
            "from os import environ; ",
            "from importlib import import_module; ",
            f"sys.argv = {argv!r}; sys.path.append('src');",
            f"{self.format_args_class(self.named_args)}",
            f"result = import_module('{target_module}').{function_call};",
        ]

        if self.options.get("print_result"):
            script.append(f"result is not None and print(result);")

        # Exactly which python executable to use is usually resolved by the executor
        cmd = ("python", "-c", "".join(script))

        self._print_action(" ".join(argv), context.dry)
        return context.get_executor(self.invocation, env, self.options).execute(
            cmd, use_exec=self.options.get("use_exec", False)
        )

    @classmethod
    def _validate_task_def(
        cls, task_name: str, task_def: Dict[str, Any], config: "PoeConfig"
    ) -> Optional[str]:
        try:
            target_module, target_ref = task_def["script"].split(":", 1)
            if not target_ref.isidentifier():
                parse_and_validate(target_ref)
        except (ValueError, ScriptParseError):
            return (
                f"Task {task_name!r} contains invalid callable reference "
                f"{task_def['script']!r} (expected something like `module:callable`"
                " or `module:callable()`)"
            )

        return None

    def parse_script_content(self, args: Optional[Dict[str, Any]]) -> Tuple[str, str]:
        """
        Returns the module to load, and the function call to execute.

        Will raise an exception if the function call contains invalid syntax or references
        variables that are not in scope.
        """
        try:
            target_module, target_ref = self.content.strip().split(":", 1)
        except ValueError:
            raise ScriptParseError(f"Invalid task content: {self.content.strip()!r}")

        if target_ref.isidentifier():
            if args:
                return target_module, f"{target_ref}(**({args}))"
            return target_module, f"{target_ref}()"

        function_call = resolve_function_call(target_ref, set(args or tuple()))
        # Strip out any new lines because they can be problematic on windows
        function_call = re.sub(r"((\r\n|\r|\n) | (\r\n|\r|\n))", " ", function_call)
        function_call = re.sub(r"(\r\n|\r|\n)", " ", function_call)

        return target_module, function_call

    @staticmethod
    def format_args_class(
        named_args: Optional[Dict[str, Any]], classname: str = "__args"
    ) -> str:
        """
        Generates source for a python class with the entries of the given dictionary
        represented as class attributes.
        """
        if named_args is None:
            return ""
        return (
            f'{classname}=type("{classname}",(object,),'
            "{"
            + ",".join(f"{name!r}:{value!r}" for name, value in named_args.items())
            + "});"
        )
