import argparse
import os
from pathlib import Path
import toml
import sys
from typing import Any, Dict


def _read_pyproject(path: str) -> Dict[str, Any]:
    with open(Path(path).resolve(), "r") as prproj:
        return toml.load(prproj)


def load_tasks(path: str) -> Dict[str, str]:
    # TODO: handle errors
    return _read_pyproject(path)["tool"]["poe"]["tasks"]


def validate_tasks(tasks: Dict[str, str]) -> Dict[str, str]:
    """
    TODO: return summary of invalid tasks
    """
    pass


def get_parser():
    # TODO: support passing options to poe before the task name

    parser = argparse.ArgumentParser(
        description="Poe the Poet - A task runner that works well with poetry."
    )
    task_parser = parser.add_subparsers(title="task", dest="task")
    task_parser.add_parser("", description="task")

    print(parser.parse_args())


def main():
    # TODO: print help if no toml or an invalid toml is found
    # TODO: print help and list tasks if no task specified
    # TODO: print help and list issues if tasks are invalid
    # TODO: support specifying an alterivate project root

    pyproject_path = Path(".").resolve().joinpath("pyproject.toml")
    tasks = load_tasks(pyproject_path)
    # args = get_parser()
    # validate_tasks(tasks)

    # TODO: handle miss
    selected_task = sys.argv[1]
    script = tasks[selected_task]

    print("poe:", tasks[selected_task])

    os.system(script + " " + " ".join(sys.argv[2:]))
