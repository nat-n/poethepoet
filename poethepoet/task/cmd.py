from __future__ import annotations

import os
import shlex
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any, Literal

from ..exceptions import ConfigValidationError, ExecutionError, PoeException
from .base import PoeTask

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext
    from ..env.task_env import TaskEnv
    from ..executor.task_run import PoeTaskRun
    from .base import TaskSpecFactory

_PATH_SEPARATORS = os.sep + (os.altsep or "")


class CmdTask(PoeTask):
    """
    Executes a single command as a subprocess without a shell. Supports glob
    patterns for filesystem paths, parameter expansion of environment variable
    or private variables.
    """

    __key__ = "cmd"

    # Track if we encountered a glob pattern when parsing the command line
    __passed_unmatched_glob = False

    class TaskOptions(PoeTask.TaskOptions):
        use_exec: bool = False
        """
        Specify that this task should be executed in the same process, instead of
        as a subprocess. Note: This feature has limitations, such as not being
        compatible with tasks that are referenced by other tasks and not working on
        Windows.
        """

        empty_glob: Literal["pass", "null", "fail"] = "pass"
        """
        Determines how to handle glob patterns with no matches. The default is
        'pass', which causes unmatched patterns to be passed through to the command
        (just like in bash). Setting it to 'null' will replace an unmatched pattern
        with nothing, and setting it to 'fail' will cause the task to fail with an
        error if there are no matches.
        """

        ignore_fail: bool | list[int] = False
        """
        Return exit code 0 even if the task fails, or specify a list of task exit
        codes to ignore.
        """

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
        options: CmdTask.TaskOptions

        def _task_validations(self, config: PoeConfig, task_specs: TaskSpecFactory):
            """
            Perform validations on this TaskSpec that apply to a specific task type
            """
            if not self.content.strip():
                raise ConfigValidationError("Task has no content")

    @classmethod
    def __schema_fragment__(cls, ctx: Any) -> dict:
        """
        Override: attach a SchemaStore-style title and shell-command
        examples on the ``cmd`` discriminator field, and forbid the
        ``use_exec`` + ``capture_stdout`` combination (runtime
        ``TaskOptions.validate`` rejects it too).
        """
        fragment = super().__schema_fragment__(ctx)
        fragment["properties"]["cmd"]["title"] = "Command to execute"
        fragment["properties"]["cmd"]["examples"] = [
            "rm -rf ./**/*.pyc",
            "echo Hello ${USER}",
            "echo Hello \\${USER}",
        ]
        fragment["if"] = {
            "properties": {"use_exec": {"const": True}},
            "required": ["use_exec"],
        }
        # Encode the forbidden property as `{capture_stdout: false}`
        # rather than `{not: {required: [capture_stdout]}}`: semantically
        # identical, but the later fails ajv's strictRequired in schemastore
        fragment["then"] = {"properties": {"capture_stdout": False}}
        return fragment

    spec: TaskSpec

    async def _handle_run(
        self, context: RunContext, env: TaskEnv, task_state: PoeTaskRun
    ):
        if ignore_fail := self.spec.options.ignore_fail:
            task_state.ignore_failure(ignore_fail)

        extra_args = self._parse_and_register_args(env)

        executor = self._get_executor(context, env)

        if self._content_uses_extra_args():
            cmd = tuple(self._resolve_commandline(context, env))
        else:
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

    def _parse_content(self):
        if self._parsed_content is None:
            from ..helpers.parse import parse_poe_cmd
            from ..helpers.parse.core import ParseError

            try:
                self._parsed_content = parse_poe_cmd(self.spec.content)
            except ParseError as error:
                raise PoeException(
                    f"Couldn't parse command line for task {self.name!r}", error
                )
        return self._parsed_content

    def _resolve_commandline(self, context: RunContext, env: TaskEnv):
        self.__passed_unmatched_glob = False

        command_lines = self._parse_content().command_lines

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
        for line in command_lines:
            for cmd_token, glob_pattern in line.resolve_tokens(env):
                if glob_pattern is None:
                    result.append(cmd_token)
                    continue

                # Resolve glob pattern from the working directory, or from the
                # filesystem root if the pattern is absolute
                glob_root, pattern = self._split_glob_pattern(working_dir, glob_pattern)
                try:
                    matches = [str(match) for match in glob_root.glob(pattern)]
                except (ValueError, NotImplementedError, OSError) as error:
                    raise ExecutionError(
                        f"Failed to expand glob pattern {cmd_token!r} in cmd task "
                        f"{self.name!r}",
                        error,
                    )

                if matches:
                    result.extend(matches)
                elif self.spec.options.empty_glob == "fail":
                    searched_in = (
                        f" in working directory {working_dir!s}"
                        if glob_root == working_dir
                        else ""
                    )
                    raise ExecutionError(
                        f"Glob pattern {cmd_token!r} did not match any files"
                        f"{searched_in}"
                    )
                elif self.spec.options.empty_glob == "pass":
                    # If the glob pattern does not match any files, we just pass the
                    # token through as it would be without the pattern
                    self.__passed_unmatched_glob = True
                    result.append(cmd_token)

        return result

    @staticmethod
    def _split_glob_pattern(working_dir: Path, pattern: str) -> tuple[Path, str]:
        """
        Translate a glob pattern into the directory to search from and a relative
        pattern that pathlib will accept across all supported python versions.

        - pathlib only supports relative patterns, so an absolute pattern is split
          into its anchor (e.g. "/" or "C:\\") to search from and the remainder.
        - before python 3.13 pathlib rejects "**" unless it is a whole path
          component, so anywhere else we collapse it to "*", which is how newer
          python versions (and bash without globstar) interpret it. Literal stars
          are already escaped as "[*]" so they are unaffected.
        """
        glob_root = working_dir
        if anchor := PurePath(pattern).anchor:
            glob_root = Path(anchor)
            pattern = pattern[len(anchor) :].lstrip(_PATH_SEPARATORS)

        if "**" in pattern:
            import re

            pattern = "".join(
                part if part == "**" else re.sub(r"\*{2,}", "*", part)
                for part in re.split(f"([{re.escape(_PATH_SEPARATORS)}])", pattern)
            )

        return glob_root, pattern
