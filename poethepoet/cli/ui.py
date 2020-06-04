import argparse
import os
from pastel import add_style, colorize
import sys
from typing import Iterable, List, Optional, Sequence, Union
from .util import PoeException
from ..__version__ import __version__


ENABLE_ANSI_DEFAULT = (
    (sys.platform != "win32" or "ANSICON" in os.environ)
    and hasattr(sys.stdout, "isatty")
    and sys.stdout.isatty()
)


add_style("u", "default", options="underline")
add_style("em", "cyan")
add_style("em2", "cyan", options="italic")
add_style("dem", "black", options="dark")
add_style("h2", "default", options="bold")
add_style("h2-dim", "default", options="dark")
add_style("stripe", bg="blue")
add_style("error", "light_red", options="bold")


def get_argparser(tasks: Iterable[str] = tuple(), minimal: bool = False):
    parser = argparse.ArgumentParser(
        prog="poe",
        description="Poe the Poet: A task runner that works well with poetry.",
        add_help=False,
        allow_abbrev=False,
        formatter_class=PoeHelpFormatter,
    )

    parser.add_argument(
        "-h",
        "--help",
        dest="help",
        action="store_true",
        default=False,
        help="Show this help page and exit",
    )

    if not minimal:
        verbosity_group = parser.add_mutually_exclusive_group()
        verbosity_group.add_argument(
            "-v",
            "--verbose",
            dest="verbosity",
            action="store_const",
            metavar="verbose_mode",
            const="1",
            help="More console spam",
        )
        verbosity_group.add_argument(
            "-q",
            "--quiet",
            dest="verbosity",
            action="store_const",
            metavar="quiet_mode",
            default=0,
            const="-1",
            help="Less console spam",
        )

    parser.add_argument(
        "--root",
        dest="project_root",
        metavar="PATH",
        type=str,
        default=None,
        help="Specify where to find the pyproject.toml",
    )

    ansi_group = parser.add_mutually_exclusive_group()
    ansi_group.add_argument(
        "--ansi",
        dest="ansi",
        action="store_true",
        default=ENABLE_ANSI_DEFAULT,
        help="Force enable ANSI output",
    )
    ansi_group.add_argument(
        "--no-ansi",
        dest="ansi",
        action="store_false",
        default=ENABLE_ANSI_DEFAULT,
        help="Force disable ANSI output",
    )

    if not minimal:
        parser.add_argument("task", default=tuple(), nargs=argparse.REMAINDER)

    return parser


def get_minimal_args():
    """
    Parse just the --root optional argument if given
    """
    parser = get_argparser(minimal=True)
    return parser.parse_known_args()[0]


class SubcommandParser(argparse.ArgumentParser):
    """
    This subparser puts all remaining arguments in task_args attribute of
    namespace as a workaround for a limitation/bug of argparse as discussed here:
    https://stackoverflow.com/questions/43219022/using-argparse-remainder-at-beginning-of-parser-sub-parser
    """

    def parse_known_args(self, args=None, namespace=None):
        if namespace is None:
            namespace = argparse.Namespace()
        setattr(namespace, "task_args", args)
        return namespace, []


class PoeHelpFormatter(argparse.HelpFormatter):
    pass


def format_help(
    parser,
    tasks: Iterable[str] = tuple(),
    info: Optional[str] = None,
    error: Optional[PoeException] = None,
):
    # TODO: See if this can be done nicely with a custom HelpFormatter
    # TODO: a lower verbosity version of this for certain situations

    result: List[Union[str, Sequence[str]]] = [
        (
            "Poe the Poet - A task runner that works well with poetry.",
            f"version <em>{__version__}</em>",
        )
    ]
    if info:
        result.append(f"{f'<em2>Result: {info}</em2>'}")
    if error:
        result.append([f"<error>Error: {error.msg} </error>"])
        if error.cause:
            result[-1].append(f"<error> From: {error.cause} </error>")  # type: ignore

    # Use argparse for usage summary
    result.append(
        (
            "<h2>USAGE</h2>",
            "  <u>poe</u> [-h] [-v | -q] [--root PATH] [--ansi | --no-ansi] task [task arguments]",
        )
    )

    # Use argparse for optional args
    formatter = parser.formatter_class(prog=parser.prog)
    action_group = parser._action_groups[1]
    formatter.start_section(action_group.title)
    formatter.add_arguments(action_group._group_actions)
    formatter.end_section()
    result.append(("<h2>GLOBAL OPTIONS</h2>", *formatter.format_help().split("\n")[1:]))

    if tasks:
        tasks_section = ["<h2>CONFIGURED TASKS</h2>"]
        for task in tasks:
            if task.startswith("_"):
                continue
            tasks_section.append(f"  <em>{task}<em>")
        result.append(tasks_section)
    else:
        result.append("<h2-dim>NO TASKS CONFIGURED</h2-dim>")

    return colorize(
        "\n\n".join(
            section if isinstance(section, str) else "\n".join(section).strip("\n")
            for section in result
        )
        + "\n"
    )
