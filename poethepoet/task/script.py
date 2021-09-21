import re
from typing import (
    Any,
    Dict,
    Optional,
    MutableMapping,
    Tuple,
    Type,
    TYPE_CHECKING,
    Sequence,
    Union,
)
from .base import PoeTask
from ..helpers.python import format_args_class, parse_script_content

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext


_FUNCTION_CALL_PATTERN = re.compile(r"^(.+)\((.*)\)\s*;?\s*$")


class ScriptTask(PoeTask):
    """
    A task consisting of a reference to a python script
    """

    content: str

    __key__ = "script"
    __options__: Dict[str, Type] = {}

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: MutableMapping[str, str],
    ) -> int:
        # TODO: check whether the project really does use src layout, and don't do
        #       sys.path.append('src') if it doesn't
        named_args = self.parse_named_args(extra_args)
        target_module, function_call = parse_script_content(self.content, named_args)
        argv = [
            self.name,
            *(self._resolve_envvars(token, env) for token in extra_args),
        ]
        cmd = (
            "python",
            "-c",
            "import sys; "
            "from importlib import import_module; "
            f"sys.argv = {argv!r}; sys.path.append('src');"
            f"\n{format_args_class(named_args)}"
            f"import_module('{target_module}').{function_call}",
        )

        print("cmd", cmd)  # TODO: remove

        self._print_action(" ".join(argv), context.dry)
        return context.get_executor(self.invocation, env, self.options).execute(cmd)

    @classmethod
    def _parse_content(
        cls, call_ref: str
    ) -> Union[Tuple[str, str, Optional[str]], Tuple[None, None, None]]:
        """
        Parse module and callable call from a string like one of:
         - "some_module:main"
         - "some.module:main(foo='bar')"
        """
        try:
            target_module, target_ref = call_ref.split(":")
        except ValueError:
            return None, None, None

        if target_ref.isidentifier():
            return target_module, f"{target_ref}", None

        call_match = _FUNCTION_CALL_PATTERN.match(target_ref)
        if call_match:
            callable_name, call_params = call_match.groups()
            return target_module, callable_name, call_params

        return None, None, None

    @classmethod
    def _validate_task_def(
        cls, task_name: str, task_def: Dict[str, Any], config: "PoeConfig"
    ) -> Optional[str]:
        target_module, target_callable, _ = cls._parse_content(task_def["script"])
        if not target_module or not target_callable:
            return (
                f"Task {task_name!r} contains invalid callable reference "
                f"{task_def['script']!r} (expected something like `module:callable()`)"
            )
        return None

    @classmethod
    def _resolve_args(cls, call_params: str, named_args: Dict[str, str]):
        def resolve_param(param: str):
            if "=" in param:
                keyword, value = (token.strip() for token in param.split(r"=", 1))
                return {keyword: named_args.get(value, value)}
            else:
                return {param: named_args.get(param, param)}

        # I only want to filter out the empty strings that can come from the parser of named_args without having to modify named args
        # test_script_task_omit_kwarg is an example of why this is necessary -- without removing the '' we have inconsistant behavior
        # even if the arg isn't passed to poe it will be otherwise created here with an '' value
        return {
            key: value
            for param in call_params.split(",")
            for key, value in resolve_param(param.strip()).items()
            if value is not None
        }
