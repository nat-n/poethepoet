import shlex
from typing import TYPE_CHECKING

from ..exceptions import ConfigValidationError, PoeException
from .base import PoeTask

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext
    from ..env.manager import EnvVarsManager
    from .base import TaskSpecFactory


class CmdTask(PoeTask):
    """
    A task consisting of a reference to a shell command
    """

    __key__ = "cmd"

    class TaskOptions(PoeTask.TaskOptions):
        use_exec: bool = False

        def validate(self):
            """
            Validation rules that don't require any extra context go here.
            """
            super().validate()
            if self.use_exec and self.capture_stdout:
                raise ConfigValidationError(
                    "'use_exec' and 'capture_stdout'"
                    " options cannot be both provided on the same task."
                )

    class TaskSpec(PoeTask.TaskSpec):
        content: str
        options: "CmdTask.TaskOptions"

        def _task_validations(self, config: "PoeConfig", task_specs: "TaskSpecFactory"):
            """
            Perform validations on this TaskSpec that apply to a specific task type
            """
            if not self.content.strip():
                raise ConfigValidationError("Task has no content")

    spec: TaskSpec

    def _handle_run(
        self,
        context: "RunContext",
        env: "EnvVarsManager",
    ) -> int:
        named_arg_values, extra_args = self.get_parsed_arguments(env)
        env.update(named_arg_values)

        cmd = (*self._resolve_commandline(context, env), *extra_args)

        self._print_action(shlex.join(cmd), context.dry)

        return self._get_executor(context, env).execute(
            cmd, use_exec=self.spec.options.get("use_exec", False)
        )

    def _resolve_commandline(self, context: "RunContext", env: "EnvVarsManager"):
        from ..helpers.command import parse_poe_cmd, resolve_command_tokens
        from ..helpers.command.ast_core import ParseError

        try:
            command_lines = parse_poe_cmd(self.spec.content).command_lines
        except ParseError as error:
            raise PoeException(
                f"Couldn't parse command line for task {self.name!r}: {error.args[0]}"
            ) from error

        if not command_lines:
            raise PoeException(
                f"Invalid cmd task {self.name!r} does not include any command lines"
            )
        if len(command_lines) > 1:
            raise PoeException(
                f"Invalid cmd task {self.name!r} includes multiple command lines"
            )

        working_dir = self.get_working_dir(env)

        result = []
        for cmd_token, has_glob in resolve_command_tokens(
            command_lines[0], env.to_dict()
        ):
            if has_glob:
                # Resolve glob pattern from the working directory
                result.extend([str(match) for match in working_dir.glob(cmd_token)])
            else:
                result.append(cmd_token)

        return result
