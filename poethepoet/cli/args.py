import argparse
from typing import Iterable


def get_argparser(tasks: Iterable[str]):
    parser = argparse.ArgumentParser(
        prog="poe",
        description="A task runner that works well with poetry.",
        allow_abbrev=False,
    )
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
        type=str,
        default=None,
        help="Specify where to find the pyproject.toml",
    )
    tasks_subparsers = parser.add_subparsers(
        title="task", dest="task", help="The task to run", parser_class=SubcommandParser
    )
    for task in tasks:
        if task.startswith("_"):
            # Tasks with names starting with `_` are not exposed
            continue
        tasks_subparsers.add_parser(task)
    return parser


def get_root_arg():
    """
    Parse just the --root optional argument if given
    """
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument(
        "--root",
        dest="project_root",
        type=str,
        default=None,
        help="Specify where to find the pyproject.toml",
    )
    return parser.parse_known_args()[0].project_root


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
