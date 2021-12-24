# pylint: disable=import-error

from cleo.commands.command import Command
from pathlib import Path
from poetry.console.application import Application, COMMANDS
from poetry.plugins.application_plugin import ApplicationPlugin
import sys
from typing import Any, Dict

from .exceptions import PoePluginException


class PoeCommand(Command):
    prefix: str

    def __init__(self):
        super().__init__()
        # bypass cleo's option parsing
        self._ignore_validation_errors = True

    def handle(self):
        from .app import PoeThePoet

        # Get args to pass to poe
        tokenized_input = self.io.input._tokens
        task_name = tokenized_input[0][len(self.prefix) :].strip()
        task_args = tokenized_input[1:]

        app = PoeThePoet(cwd=Path(".").resolve(), output=sys.stdout)
        task_status = app(cli_args=(task_name, *task_args))
        if task_status:
            raise SystemExit(task_status)


class PoetryPlugin(ApplicationPlugin):
    def activate(self, application: Application) -> None:
        poe_config = self.get_config(application)
        command_prefix = poe_config.get("poetry_command", "poe")
        self._validate_command_prefix(command_prefix)

        if command_prefix in COMMANDS:
            raise PoePluginException(
                f"The configured command prefix {command_prefix!r} conflicts with a "
                "poetry command. Please configure a different command prefix."
            )

        if command_prefix == "":
            for task_name, task in poe_config.get("tasks", {}).items():
                if task_name in COMMANDS:
                    raise PoePluginException(
                        f"Poe task {task_name!r} conflicts with a poetry command. "
                        "Please rename the task or the configure a command prefix."
                    )
                self.register_command(application, task_name, task)
        else:
            for task_name, task in poe_config.get("tasks", {}).items():
                self.register_command(
                    application, task_name, task, f"{command_prefix} "
                )

    def _validate_command_prefix(self, command_prefix: str):
        if command_prefix and not command_prefix.isalnum():
            raise PoePluginException(
                "Provided value in pyproject.toml for tool.poe.poetry_command "
                f"{command_prefix!r} is invalid. Only alphanumeric values are allowed."
            )

    def register_command(
        self, application: Application, task_name: str, task: Any, prefix: str = ""
    ):
        command_name = prefix + task_name
        task_help = task.get("help", "") if isinstance(task, dict) else ""
        application.command_loader.register_factory(
            command_name,
            type(
                task_name.replace("-", "").capitalize() + "Command",
                (PoeCommand,),
                {"name": command_name, "description": task_help, "prefix": prefix},
            ),
        )

    @classmethod
    def get_config(cls, application: Application) -> Dict[str, Any]:
        try:
            pyproject = application.poetry.pyproject.data

        # pylint: disable=bare-except
        except:
            # Fallback to loading the config again in case of future failure of the
            # above undocumented API
            import tomlkit
            from .config import PoeConfig

            pyproject = tomlkit.loads(
                Path(PoeConfig().find_pyproject_toml()).read_text()
            )

        return pyproject.get("tool", {}).get("poe", {})
