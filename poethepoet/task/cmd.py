from typing import TYPE_CHECKING, Dict, Sequence, Tuple, Type, Union

from ..exceptions import PoeException
from .base import PoeTask

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext
    from ..env.manager import EnvVarsManager


class CmdTask(PoeTask):
    """
    A task consisting of a reference to a shell command
    """

    content: str

    __key__ = "cmd"
    __options__: Dict[str, Union[Type, Tuple[Type, ...]]] = {
        "use_exec": bool,
    }

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: "EnvVarsManager",
    ) -> int:
        named_arg_values = self.get_named_arg_values(env)
        env.update(named_arg_values)

        if named_arg_values:
            # If named arguments are defined then pass only arguments following a double
            # dash token: `--`
            try:
                split_index = extra_args.index("--")
                extra_args = extra_args[split_index + 1 :]
            except ValueError:
                extra_args = tuple()

        cmd = (*self._resolve_args(context, env), *extra_args)

        self._print_action(" ".join(cmd), context.dry)

        return context.get_executor(self.invocation, env, self.options).execute(
            cmd, use_exec=self.options.get("use_exec", False)
        )

    def _resolve_args(self, context: "RunContext", env: "EnvVarsManager"):
        from glob import glob

        from ..helpers.command import parse_poe_cmd, resolve_command_tokens

        command_lines = parse_poe_cmd(self.content).command_lines

        if not command_lines:
            raise PoeException(
                f"Invalid cmd task {self.name!r} does not include any command lines"
            )
        if len(command_lines) > 1:
            raise PoeException(
                f"Invalid cmd task {self.name!r} includes multiple command lines"
            )

        result = []
        for cmd_token, has_glob in resolve_command_tokens(
            command_lines[0], env.to_dict()
        ):
            if has_glob:
                # Resolve glob path
                # TODO: check whether cwd is correct here??
                result.extend(glob(cmd_token, recursive=True))
            else:
                result.append(cmd_token)

        return result
