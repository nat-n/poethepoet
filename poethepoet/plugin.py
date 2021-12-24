import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterator

import tomlkit

from cleo.commands.command import Command
from poetry.console import application as app
from poetry.plugins.application_plugin import ApplicationPlugin

from . import config


def get_poe_task_names() -> Iterator[str]:
    return (
        name
        for name in tomlkit.loads(
            Path(config.PoeConfig().find_pyproject_toml()).read_text()
        )["tool"]["poe"]["tasks"].keys()
        # Make sure it doesn't override default poetry commands
        if name not in app.COMMANDS
    )


def run_poe_task(name: str, io) -> int:
    # Hacks to use Cleo's IO
    io.fileno = sys.stdin.fileno  # Monkey patches io because subprocess needs it
    stdin = io
    io.fileno = sys.stdout.fileno
    stdout = io
    io.error_output.fileno = sys.stdout.fileno
    stderr = io.error_output

    return subprocess.run(
        [shutil.which("poe"), name],
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        check=False,
    ).returncode


class PoePlugin(ApplicationPlugin):
    def activate(self, application: app.Application) -> None:
        io = application.create_io()
        # Create seperate commands per task
        for task_name in get_poe_task_names():
            application.command_loader.register_factory(
                task_name,
                type(
                    task_name.replace("-", "_").capitalize() + "Command",
                    (Command,),
                    {
                        "name": task_name,
                        "handle": lambda inner_self: run_poe_task(inner_self.name, io),
                    },
                ),
            )
