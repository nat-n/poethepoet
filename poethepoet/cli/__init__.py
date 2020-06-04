import io
import os
from pathlib import Path
import pastel
import toml
import sys
from typing import Any, Dict, Iterable, MutableMapping, Optional
from .ui import format_help, get_argparser, get_minimal_args
from .util import PoeException
from ..task import PoeTask, TaskDef

TOML_NAME = "pyproject.toml"


def _read_pyproject(path: Path) -> MutableMapping[str, Any]:
    try:
        with open(path.resolve(), "r") as prproj:
            return toml.load(prproj)
    except toml.TomlDecodeError as error:
        raise PoeException(f"Couldn't parse toml file at {path}", error) from error
    except Exception as error:
        raise PoeException(f"Couldn't open file at {path}") from error


def validate_poe_config(config: MutableMapping[str, Any]):
    supported_keys = {"run_in_project_root", "tasks"}
    unsupported_keys = set(config) - supported_keys
    if unsupported_keys:
        raise PoeException(f"Unsupported keys in poe config: {unsupported_keys!r}")
    if not isinstance(config.get("run_in_project_root", True), bool):
        raise PoeException(
            "Unsupported value for option `run_in_project_root` "
            f"{config['run_in_project_root']!r}"
        )


def load_poe_config(path: Path) -> MutableMapping[str, Any]:
    try:
        return _read_pyproject(path)["tool"]["poe"]
    except KeyError as error:
        raise PoeException("No poe configuration found in file at pyproject.toml")


def find_pyproject_toml(target_dir: Optional[str] = None) -> Path:
    """
    Resolve a path to a pyproject.toml using one of two strategies:
      1. If target_dir is provided then only look there, (accept path to .toml file or
         to a directory dir).
      2. Otherwise look for the pyproject.toml is the current working directory,
         following by all parent directories in ascending order.

    Both strategies result in an Exception on failure.
    """
    if target_dir:
        target_path = Path(target_dir).resolve()
        if not target_path.name.endswith(".toml"):
            target_path = target_path.joinpath(TOML_NAME)
        if not target_path.exists():
            raise PoeException(
                "Poe could not find a pyproject.toml file at the given location: "
                f"{target_dir}"
            )
        return target_path

    maybe_result = Path(".").resolve().joinpath(TOML_NAME)
    while not maybe_result.exists():
        if maybe_result.parent == Path("/"):
            raise PoeException(
                "Poe could not find a pyproject.toml file in /Users/nat/Projects or its"
                " parents"
            )
        maybe_result = maybe_result.parents[1].joinpath(TOML_NAME).resolve()
    return maybe_result


def validate_task_defs(task_defs: Dict[str, TaskDef]) -> Dict[str, str]:
    """Validate tasks from toml file"""
    result = {}
    for task_name, task_def in task_defs.items():
        error = PoeTask.validate_def(task_name, task_def)
        if error is not None:
            result[task_name] = error
    return result


def main() -> int:
    minimal_args = get_minimal_args()
    # Configure whether we're going to use colors
    pastel.with_colors(minimal_args.ansi)

    try:
        pyproject_path = find_pyproject_toml(minimal_args.project_root)
        poe_config = load_poe_config(pyproject_path)
        validate_poe_config(poe_config)
    except PoeException as error:
        if minimal_args.help:
            print(format_help(get_argparser()))
            return 0
        print(format_help(get_argparser(), error=error))
        return 1

    project_dir = pyproject_path.parent
    task_defs: Dict[str, TaskDef] = poe_config.get("tasks", {})
    parser = get_argparser(task_defs.keys())
    args = parser.parse_args()

    if args.help:
        print(format_help(parser, tasks=task_defs))
        return 0

    invalid_tasks = validate_task_defs(task_defs)
    if invalid_tasks:
        print(
            format_help(
                parser,
                tasks=task_defs,
                error=PoeException(next(iter(invalid_tasks.values()))),
            )
        )
        return 1

    if not args.task:
        print(format_help(parser, tasks=task_defs, info="No task specified."))
        return 1

    take_name, *take_args = args.task

    if args.task[0] not in task_defs:
        print(
            format_help(
                parser,
                tasks=task_defs,
                error=PoeException(f"Unrecognised task {args.task[0]!r}"),
            )
        )
        return 1

    task = PoeTask.from_def(args.task, task_defs[take_name])
    task.run(
        take_args,
        env=dict(os.environ, POE_ROOT=str(project_dir)),
        project_dir=project_dir,
        set_cwd=poe_config.get("run_in_project_root", True),
    )
    return 0
