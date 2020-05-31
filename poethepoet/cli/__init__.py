import io
import os
from pathlib import Path
import toml
import sys
from typing import Any, Dict, Iterable, MutableMapping, Optional
from .args import get_argparser, get_root_arg
from ..task import PoeTask, TaskDef

TOML_NAME = "pyproject.toml"


def _read_pyproject(path: str) -> MutableMapping[str, Any]:
    with open(Path(path).resolve(), "r") as prproj:
        return toml.load(prproj)


def load_tasks(path: str) -> MutableMapping[str, str]:
    # TODO: handle errors: permissions etc, or no poe section
    return _read_pyproject(path)["tool"]["poe"]


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


def validate_task_defs(
    task_defs: Dict[str, TaskDef], output: Optional[io.TextIOBase]
) -> bool:
    # Validate tasks from toml file
    has_errors = False
    for task_name, task_def in task_defs.items():
        error = PoeTask.validate_def(task_name, task_def)
        if error is not None:
            has_errors = True
            if output is not None:
                output.write(f"Poe config error: {error}\n")  # TODO: use ansi style
    return has_errors


def main():
    # TODO: print help if no toml or an invalid toml is found
    # TODO: print help and list tasks if no task specified
    # TODO: print help and list issues if tasks are invalid

    project_root_arg = get_root_arg()
    pyproject_path = find_pyproject_toml(project_root_arg)
    project_dir = pyproject_path.parent
    poe_config = load_tasks(pyproject_path)
    task_defs = poe_config["tasks"]
    parser = get_argparser(task_defs.keys())
    args = parser.parse_args()

    if validate_task_defs(task_defs, sys.stderr):
        raise SystemExit(1)

    if args.task is None:
        parser.error("No task given!")

    task = PoeTask.from_def(args.task, task_defs[args.task])
    task.run(
        args.task_args,
        env=dict(os.environ, POE_ROOT=str(project_dir)),
        project_dir=project_dir,
        set_cwd=poe_config.get("run_in_project_root", False),
    )


class PoeException(Exception):
    pass
