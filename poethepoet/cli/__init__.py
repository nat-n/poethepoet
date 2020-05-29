import os
from pathlib import Path
import toml
import sys
from typing import Any, Dict, Iterable, MutableMapping


def _read_pyproject(path: str) -> MutableMapping[str, Any]:
    with open(Path(path).resolve(), "r") as prproj:
        return toml.load(prproj)


def load_tasks(path: str) -> MutableMapping[str, str]:
    # TODO: handle errors
    return _read_pyproject(path)["tool"]["poe"]["tasks"]


def validate_tasks(tasks: Dict[str, str]) -> Dict[str, str]:
    """
    TODO: return summary of invalid tasks
    """
    pass


def is_poetry_active():
    # TODO: work out how to make this work inside poetry run commands
    return bool(os.environ.get("POETRY_ACTIVE"))


def get_command(script: str, extra_args: Iterable[str], poetry_active: bool):
    if poetry_active:
        return f"{script} {' '.join(extra_args)}"
    return f"poetry run {script} {' '.join(extra_args)}"


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

    cmd = get_command(script, sys.argv[2:], is_poetry_active())

    # TODO: support option for qiete mode
    print("poe:", script)

    # TODO: maybe not the most appropriate way to shell out
    os.system(cmd)
