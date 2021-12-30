# pylint: disable=import-error

from cleo.commands.command import Command
from pathlib import Path
from poetry.console.application import Application, COMMANDS
from poetry.plugins.application_plugin import ApplicationPlugin
from typing import Any, Dict, List

from .exceptions import PoePluginException


class PoeCommand(Command):
    prefix: str

    def __init__(self):
        super().__init__()
        # bypass cleo's option parsing
        self._ignore_validation_errors = True

    def _get_argv(self):
        """
        Get args to pass to poe

        Discard any tokens prefixed with "-" preceding the task name.
        """
        tokenized_input = self.io.input._tokens[:]
        task_name_index = _index_of_first_non_option(tokenized_input)
        tokenized_input = tokenized_input[task_name_index:]
        task_name = tokenized_input[0][len(self.prefix) :].strip()
        task_args = tokenized_input[1:]
        return (task_name, *task_args) if task_name else task_args

    def handle(self):
        from .app import PoeThePoet
        from .config import PoeConfig

        try:
            from poetry.utils.env import EnvManager

            poetry_env_path = EnvManager(self.application.poetry).get().path
        # pylint: disable=bare-except
        except:
            poetry_env_path = None

        cwd = Path(".").resolve()
        config = PoeConfig(cwd=cwd)

        if self.io.output.is_quiet():
            config._baseline_verbosity = -1
        elif self.io.is_very_verbose():
            config._baseline_verbosity = 2
        elif self.io.is_verbose():
            config._baseline_verbosity = 1

        app = PoeThePoet(
            cwd=cwd,
            config=config,
            output=self.io.output.stream,
            poetry_env_path=poetry_env_path,
        )
        task_status = app(cli_args=self._get_argv())

        if task_status:
            raise SystemExit(task_status)


class PoetryPlugin(ApplicationPlugin):
    def activate(self, application: Application) -> None:
        poe_config = self._get_config(application)
        command_prefix = poe_config.get("poetry_command", "poe")
        poe_tasks = poe_config.get("tasks", {})
        self._validate_command_prefix(command_prefix)

        if command_prefix in COMMANDS:
            raise PoePluginException(
                f"The configured command prefix {command_prefix!r} conflicts with a "
                "poetry command. Please configure a different command prefix."
            )

        if command_prefix == "":
            for task_name, task in poe_tasks.items():
                if task_name in COMMANDS:
                    raise PoePluginException(
                        f"Poe task {task_name!r} conflicts with a poetry command. "
                        "Please rename the task or the configure a command prefix."
                    )
                self._register_command(application, task_name, task)
        else:
            self._register_command(
                application,
                "",
                {"help": "A task runner that works well with poetry"},
                command_prefix,
            )
            for task_name, task in poe_tasks.items():
                self._register_command(
                    application, task_name, task, f"{command_prefix} "
                )

        self._monkey_patch_cleo(command_prefix, list(poe_tasks.keys()))

    @classmethod
    def _get_config(cls, application: Application) -> Dict[str, Any]:
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

    def _validate_command_prefix(self, command_prefix: str):
        if command_prefix and not command_prefix.isalnum():
            raise PoePluginException(
                "Provided value in pyproject.toml for tool.poe.poetry_command "
                f"{command_prefix!r} is invalid. Only alphanumeric values are allowed."
            )

    def _register_command(
        self, application: Application, task_name: str, task: Any, prefix: str = ""
    ):
        command_name = prefix + task_name
        task_help = task.get("help", "") if isinstance(task, dict) else ""
        application.command_loader.register_factory(
            command_name,
            type(
                (task_name or prefix).replace("-", "").capitalize() + "Command",
                (PoeCommand,),
                {"name": command_name, "description": task_help, "prefix": prefix},
            ),
        )

    def _monkey_patch_cleo(self, prefix: str, task_names: List[str]):
        """
        Cleo is quite opinionated about CLI structure and loose about how options are
        used, and so doesn't currently support invidual commands having their own way of
        interpreting arguments, and forces them in inherit certain options from the
        application. This is a problem for poe which requires that global options are
        provided before the task name, and everything after the task name is interpreted
        ONLY in terms of the task.

        This hack monkey-patches internals of Cleo that are invoked directly after
        plugin's are loaded by poetry, and exploits a feature whereby argument and
        option parsing are effectively disabled following any occurance of a "--" on the
        command line, but parsing of the command name still works! Thus the solution is
        to detect when it is a command from this plugin that is about to be executed and
        insert the "--" token and the start of the tokens list of the ArgvInput instance
        that the application is about to read the CLI options from.

        Hopefully this doesn't get broken by a future update to poetry or cleo :S
        """

        import cleo.application

        continue_run = cleo.application.Application._run

        def _run(self, io):
            # Trick cleo to ignoring arguments and options following one of the commands
            # from this plugin by injecting a '--' token at the start of the list of
            # command line tokens
            tokens = io.input._tokens
            task_name_index = _index_of_first_non_option(tokens)
            poe_commands = (prefix,) if prefix else task_names
            if (
                0 <= task_name_index < len(tokens)
                and tokens[task_name_index] in poe_commands
            ):
                # update tokens list in place
                tokens.insert(task_name_index, "--")

            continue_run(self, io)

        # Apply the patch
        cleo.application.Application._run = _run


def _index_of_first_non_option(tokens: List[str]):
    """
    Find the index of the first token that doesn't start with `-`
    Returns len(tokens) if none is found.
    """
    return next(
        (index for index, token in enumerate(tokens) if token[0] != "-"),
        len(tokens),
    )
