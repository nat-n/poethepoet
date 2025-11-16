import shlex
from typing import TYPE_CHECKING, Literal

from ..exceptions import ConfigValidationError, ExecutionError, PoeException
from ..executor.task_run import PoeTaskRun
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

    # Track if we encountered a glob pattern when parsing the command line
    __passed_unmatched_glob = False

    class TaskOptions(PoeTask.TaskOptions):
        use_exec: bool = False
        empty_glob: Literal["pass", "null", "fail"] = "pass"

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

    async def _handle_run(
        self, context: "RunContext", env: "EnvVarsManager", task_state: PoeTaskRun
    ):
        named_arg_values, extra_args = self.get_parsed_arguments(env)
        env.update(named_arg_values)

        executor = self._get_executor(context, env)
        env.update({"POE_ACTIVE": executor.__key__})

        cmd = (*self._resolve_commandline(context, env), *extra_args)

        self._print_action(shlex.join(cmd), context.dry)

        process = await executor.execute(
            cmd, use_exec=self.spec.options.get("use_exec", False)
        )
        await task_state.add_process(process, finalize=True)

        await process.wait()
        if process.returncode != 0 and self.__passed_unmatched_glob:
            # We made a breaking change in 0.36.0 to pass through glob patterns with no
            # matches. If this might have been the cause of the failure, we print a
            # warning with a link.
            self.ctx.io.print_warning(
                "Poe task failure may be related to a breaking change in "
                "poethepoet 0.36.0 in the default handling of unmatched glob patterns. "
                "More details: https://github.com/nat-n/poethepoet/discussions/314",
            )

    def _resolve_commandline(self, context: "RunContext", env: "EnvVarsManager"):
        from ..helpers.command import parse_poe_cmd, resolve_command_tokens
        from ..helpers.command.ast_core import ParseError

        self.__passed_unmatched_glob = False

        try:
            command_lines = parse_poe_cmd(self.spec.content).command_lines
        except ParseError as error:
            raise PoeException(
                f"Couldn't parse command line for task {self.name!r}", error
            )

        if not command_lines:
            raise PoeException(
                f"Invalid cmd task {self.name!r} does not include any command lines"
            )
        if any(line.terminator == ";" for line in command_lines[:-1]):
            # lines terminated by a line break or comment are implicitly joined
            raise PoeException(
                f"Invalid cmd task {self.name!r} includes multiple command lines"
            )

        working_dir = self.get_working_dir(env)

        result = []
        for cmd_token, has_glob in resolve_command_tokens(command_lines, env):
            if has_glob:
                # Resolve glob pattern from the working directory
                if matches := [str(match) for match in working_dir.glob(cmd_token)]:
                    result.extend(matches)
                elif self.spec.options.empty_glob == "fail":
                    raise ExecutionError(
                        f"Glob pattern {cmd_token!r} did not match any files in "
                        f"working directory {working_dir!s}"
                    )
                elif self.spec.options.empty_glob == "pass":
                    # If the glob pattern does not match any files, we just pass it
                    # through as is
                    self.__passed_unmatched_glob = True
                    result.append(cmd_token)
            else:
                result.append(cmd_token)

        return result
