import ast
from typing import (
    Any,
    Dict,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)
from .base import PoeTask
from ..exceptions import ScriptParseError
from ..helpers.env import resolve_envvars
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
    __options__: Dict[str, Union[Type, Tuple[Type, ...]]] = {}

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: Mapping[str, str],
    ) -> int:
        # TODO: check whether the project really does use src layout, and don't do
        #       sys.path.append('src') if it doesn't
        target_module, function_call = self.parse_script_content(self.named_args)
        argv = [
            self.name,
            *(resolve_envvars(token, env) for token in extra_args),
        ]
        cmd = (
            "python",
            "-c",
            "import sys; "
            "from os import environ; "
            "from importlib import import_module; "
            f"sys.argv = {argv!r}; sys.path.append('src');"
            f"\n{self.format_args_class(self.named_args)}"
            f"import_module('{target_module}').{function_call}",
        )

        self._print_action(" ".join(argv), context.dry)
        return context.get_executor(self.invocation, env, self.options).execute(cmd)

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
            target_module, target_ref = self.content.split(":", 1)
        except ValueError:
            raise ScriptParseError(f"Invalid task content: {self.content!r}")

        if target_ref.isidentifier():
            if args:
                return target_module, f"{target_ref}(**({args}))"
            return target_module, f"{target_ref}()"

        return target_module, resolve_function_call(target_ref, set(args or tuple()))

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
            f"class {classname}:\n"
            + "\n".join(f"    {name} = {value!r}" for name, value in named_args.items())
            + "\n"
        )
