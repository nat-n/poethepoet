import shutil
import subprocess
from typing import Iterator

import tomlkit
from cleo.commands.command import Command
from poetry.plugins.application_plugin import ApplicationPlugin

from . import config


def get_poe_task_names() -> Iterator[str]:
    yield from tomlkit.loads(config.PoeConfig().find_pyproject_toml())["tool"]["poe"][
        "tasks"
    ].keys()


def run_poe_task(name: str):
    return subprocess.call([shutil.which("poe"), name])


class PoePlugin(ApplicationPlugin):
    def activate(self, application):
        for task_name in get_poe_task_names():  # Assume this function exists somewhere
            application.command_loader.register_factory(
                task_name,
                lambda x: type(
                    task_name.capitalize() + "Command",
                    (Command),
                    {"name": task_name, "handle": lambda self: run_poe_task(self.name)},
                    # Also assume `run_poe_task` accepts task name as an argument, runs that poe task
                    # and returns the return code of the poe task
                ),
            )
