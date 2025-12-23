import os
import sys
from collections.abc import Mapping, Sequence
from contextlib import redirect_stderr
from typing import TYPE_CHECKING

from .__version__ import __version__
from .exceptions import ConfigValidationError, ExecutionError, PoeException
from .io import PoeIO, guess_ansi_support

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace


STDOUT_ANSI_SUPPORT = guess_ansi_support(sys.stdout)


class PoeUi:
    args: "Namespace"

    def __init__(
        self,
        io: PoeIO,
        program_name: str = "poe",
        suppress_args: Sequence[str] = ("legacy_project_root",),
    ):
        self.io = io
        self.program_name = program_name
        self.suppress_args = set(suppress_args)

    def __getitem__(self, key: str):
        """Provide easy access to arguments"""
        return getattr(self.args, key, None)

    def build_parser(self) -> "ArgumentParser":
        import argparse

        parser = argparse.ArgumentParser(
            prog=self.program_name,
            description="Poe the Poet: A task runner that works well with poetry or uv",
            add_help=False,
            allow_abbrev=False,
        )

        def maybe_suppress(arg_name: str, help_text: str):
            if arg_name in self.suppress_args:
                return argparse.SUPPRESS
            return help_text

        parser.add_argument(
            "-h",
            "--help",
            dest="help",
            metavar="TASK",
            nargs="?",
            default=...,
            help=maybe_suppress(
                "help", "Show this help page and exit, optionally supply a task."
            ),
        )

        parser.add_argument(
            "--version",
            dest="version",
            action="store_true",
            default=False,
            help=maybe_suppress("version", "Print the version and exit"),
        )

        parser.add_argument(
            "-v",
            "--verbose",
            dest="increase_verbosity",
            action="count",
            default=0,
            help=maybe_suppress("verbosity", "Increase output (repeatable)"),
        )

        parser.add_argument(
            "-q",
            "--quiet",
            dest="decrease_verbosity",
            action="count",
            default=0,
            help=maybe_suppress("verbosity", "Decrease output (repeatable)"),
        )

        parser.add_argument(
            "-d",
            "--dry-run",
            dest="dry_run",
            action="store_true",
            default=False,
            help=maybe_suppress(
                "dry_run", "Print the task contents but don't actually run it"
            ),
        )

        parser.add_argument(
            "-C",
            "--directory",
            dest="project_root",
            metavar="PATH",
            type=str,
            default=os.environ.get("POE_PROJECT_DIR", None),
            help=maybe_suppress(
                "project_root", "Specify where to find the pyproject.toml"
            ),
        )

        parser.add_argument(
            "-e",
            "--executor",
            dest="executor",
            metavar="EXECUTOR",
            type=str,
            default="",
            help=maybe_suppress("executor", "Override the default task executor"),
        )

        def key_value_pair(input_str: str) -> tuple[str, str]:
            if "=" in input_str:
                key, val = input_str.split("=", 1)
                return key, val
            return input_str, "1"

        parser.add_argument(
            "-X",
            "--executor-opt",
            dest="executor_options",
            action="append",
            metavar="KEY[=VALUE]",
            default=[],
            type=key_value_pair,
            help=maybe_suppress(
                "executor_options",
                "Set executor configuration for this run.",
            ),
        )

        # legacy --root parameter, keep for backwards compatibility but help output is
        # suppressed
        parser.add_argument(
            "--root",
            dest="project_root",
            metavar="PATH",
            type=str,
            default=None,
            help=maybe_suppress(
                "legacy_project_root", "Specify where to find the pyproject.toml"
            ),
        )

        ansi_group = parser.add_mutually_exclusive_group()
        ansi_group.add_argument(
            "--ansi",
            dest="ansi",
            action="store_true",
            default=STDOUT_ANSI_SUPPORT,
            help=maybe_suppress("ansi", "Force enable ANSI output"),
        )
        ansi_group.add_argument(
            "--no-ansi",
            dest="ansi",
            action="store_false",
            default=STDOUT_ANSI_SUPPORT,
            help=maybe_suppress("ansi", "Force disable ANSI output"),
        )

        parser.add_argument("task", default=tuple(), nargs=argparse.REMAINDER)

        return parser

    def parse_args(self, cli_args: Sequence[str]):
        self.parser = self.build_parser()

        with redirect_stderr(self.io.error_output):
            self.args = self.parser.parse_args(cli_args)

        self.io.configure(ansi_enabled=self.args.ansi)
        self.io.configure(
            offset=(self.args.increase_verbosity - self.args.decrease_verbosity),
            # Only respect verbosity modifier CLI flags if verbosity_offset is not
            # already set (e.g. by a plugin)
            dont_override=True,
        )

    def print_help(
        self,
        tasks: (
            Mapping[str, tuple[str, Sequence[tuple[tuple[str, ...], str, str]]]] | None
        ) = None,
        info: str | None = None,
        error: PoeException | None = None,
    ):
        # Ignore verbosity mode if help flag is set
        help_flag_set = self["help"] is None
        help_single_task = self["help"] if isinstance(self["help"], str) else None
        verbosity = 0 if help_flag_set else self.io.verbosity

        # If there's no error and verbosity wasn't explicitly decreased for this call,
        # then ensure we still print help
        if not error and not self.io.verbosity_offset_was_set:
            verbosity = min(0, self.io.verbosity)

        result: list[str | Sequence[str]] = []
        if verbosity >= 0 and not help_single_task:
            result.append((f"<h2>Poe the Poet</h2> (version <em>{__version__}</em>)",))

        if info and verbosity >= -2:
            result.append(f"{f'<em2>Result: {info}</em2>'}")

        if error and verbosity >= -2:
            result.append(self._format_poe_error(error))

        if tasks and help_single_task:
            help_text, args_help = tasks[help_single_task]
            result.append(
                self._format_single_task_help(help_single_task, help_text, args_help)
            )

        else:
            if verbosity >= 0:
                result.append(
                    (
                        "<h2>Usage:</h2>",
                        f"  <u>{self.program_name}</u>"
                        " [global options]"
                        " task [task arguments]",
                    )
                )

                # Use argparse for optional args
                formatter = self.parser.formatter_class(prog=self.parser.prog)
                action_group = self.parser._action_groups[1]
                formatter.start_section(action_group.title)
                formatter.add_arguments(action_group._group_actions)
                formatter.end_section()
                result.append(
                    (
                        "<h2>Global options:</h2>",
                        *formatter.format_help().split("\n")[1:],
                    )
                )

            if verbosity >= -1:
                if tasks:
                    max_task_len = max(
                        max(
                            len(task),
                            max(
                                [
                                    len(", ".join(str(opt) for opt in opts))
                                    for (opts, _, _) in args
                                ]
                                or (0,)
                            )
                            + 2,
                        )
                        for task, (_, args) in tasks.items()
                    )
                    col_width = max(20, min(30, max_task_len))

                    tasks_section = ["<h2>Configured tasks:</h2>"]
                    for task, (help_text, args_help) in tasks.items():
                        if task.startswith("_"):
                            continue
                        tasks_section.append(
                            f"  <em>{self._padr(task, col_width)}</em>  "
                            f"{self._align(help_text, col_width)}"
                        )
                        tasks_section.extend(
                            self._format_args_help(args_help, col_width, indent=3)
                        )

                    result.append(tasks_section)

                else:
                    result.append("<h2-dim>NO TASKS CONFIGURED</h2-dim>")

        if error and self.io.is_debug_enabled():
            import traceback

            result.append(
                "".join(
                    traceback.format_exception(type(error), error, error.__traceback__)
                ).strip()
            )

        self.io.print(
            "\n\n".join(
                section if isinstance(section, str) else "\n".join(section).strip("\n")
                for section in result
            )
            + "\n"
            + ("\n" if verbosity >= 0 else ""),
            message_verbosity=-2,
        )

    def _format_poe_error(self, error: PoeException) -> tuple[str, ...]:
        error_lines = []
        if isinstance(error, ConfigValidationError):
            if error.task_name:
                if error.context:
                    error_lines.append(f"{error.context} in task {error.task_name!r}")
                else:
                    error_lines.append(f"Invalid task {error.task_name!r}")
                if error.filename:
                    error_lines[-1] += f" in file {error.filename}"
            elif error.global_option:
                error_lines.append(f"Invalid global option {error.global_option!r}")
                if error.filename:
                    error_lines[-1] += f" in file {error.filename}"
        error_lines.extend(error.msg.split("\n"))
        if error.cause:
            error_lines.append(error.cause)
        if error.__cause__ and not isinstance(error.__cause__, SystemExit):
            error_lines.append(f"From: {error.__cause__!r}")

        return self._format_error_lines(error_lines)

    def _format_single_task_help(
        self,
        task_name: str,
        help_text: str,
        args_help: Sequence[tuple[tuple[str, ...], str, str]],
    ):
        result = [""]
        if help_text:
            result.append(f"<h2>Description:</h2>\n  {help_text.strip()}\n")

        result.extend(
            (
                "<h2>Usage:</h2>",
                f"  <u>{self.program_name}</u>"
                " [global options]"
                f" <em>{task_name}</em> [named arguments] -- [free arguments]",
                "",
            )
        )

        if args_help:
            col_width = max(20, min(30, len(task_name)))
            result.append("<h2>Named arguments:</h2>")
            result.extend(self._format_args_help(args_help, col_width))

        return "\n".join(result).rstrip()

    def _format_args_help(
        self,
        args_help: Sequence[tuple[tuple[str, ...], str, str]],
        col_width: int,
        indent: int = 1,
    ):
        for options, arg_help_text, default in args_help:
            formatted_options = ", ".join(str(opt) for opt in options)
            task_arg_help = [
                " " * indent,
                f"<em3>{self._padr(formatted_options, col_width - 1)}</em3>",
            ]
            if arg_help_text:
                task_arg_help.append(self._align(arg_help_text, col_width))
            if default:
                if "\n" in (arg_help_text or ""):
                    task_arg_help.append(
                        self._align(f"\n{default}", col_width, strip=False)
                    )
                else:
                    task_arg_help.append(default)
            yield " ".join(task_arg_help)

    @staticmethod
    def _align(text: str, width: int, *, strip: bool = True) -> str:
        text = text.replace("\n", "\n" + " " * (width + 4))
        return text.strip() if strip else text

    @staticmethod
    def _padr(text: str, width: int):
        if len(text) >= width:
            return text
        return text + " " * (width - len(text))

    def print_error(self, error: PoeException | ExecutionError):
        error_lines = error.msg.split("\n")
        if error.cause:
            error_lines.append(f"From: {error.cause}")
        if error.__cause__ and not isinstance(error.__cause__, SystemExit):
            error_lines.append(f"From: {error.__cause__!r}")

        for line in self._format_error_lines(error_lines):
            self.io.print_error(line)

        if self.io.is_debug_enabled():
            import traceback

            self.io.print_debug(
                "".join(
                    traceback.format_exception(type(error), error, error.__traceback__)
                ).strip()
            )

    def _format_error_lines(self, lines: Sequence[str]) -> tuple[str, ...]:
        return (
            f"<error>Error: {lines[0]}</error>",
            *(f"<error>     | {line}</error>" for line in lines[1:]),
        )

    def print_version(self):
        if self.io.verbosity >= 0:
            result = f"Poe the Poet - version: <em>{__version__}</em>\n"
        else:
            result = f"{__version__}\n"
        self.io.print(result, message_verbosity=-2)
