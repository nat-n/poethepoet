import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterator

import tomlkit

try:
    from cleo.commands.command import Command
    from poetry.console import application as app
    from poetry.plugins.application_plugin import ApplicationPlugin
except ModuleNotFoundError:
    app = type("application", (), {"Application": None})  # pylint: disable=C0103
    ApplicationPlugin = type(
        "ApplicationPlugin",
        (),
        {"PLUGIN_API_VERION": "1.0.0", "type": "application.plugin"},
    )

from . import config


def get_poe_task_names() -> Iterator[str]:
    return (
        name
        for name in tomlkit.loads(
            Path(config.PoeConfig().find_pyproject_toml()).read_text()
        )["tool"]["poe"]["tasks"].keys()
        if name not in app.COMMANDS
    )


def run_poe_task(name: str, io) -> int:
    io.fileno = sys.stdin.fileno
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
        if app.Application is None:
            print(
                "Poetry not found. Did you install this plugin via `poetry plugin add poethepoet[poetry_plugin]`?"
            )
            sys.exit(1)
        io = application.create_io()
        for task_name in get_poe_task_names():  # Assume this function exists somewhere
            application.command_loader.register_factory(
                task_name,
                type(
                    task_name.replace("-", "_").capitalize() + "Command",
                    (Command,),
                    {
                        "name": task_name,
                        "handle": lambda inner_self: run_poe_task(inner_self.name, io),
                    },
                    # Also assume `run_poe_task` accepts task name as an argument, runs that poe task
                    # and returns the return code of the poe task
                ),
            )
