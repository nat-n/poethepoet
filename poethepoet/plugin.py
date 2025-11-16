from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cleo.commands.command import Command
from cleo.events.console_events import COMMAND, TERMINATE
from poetry.console.application import COMMANDS, Application
from poetry.plugins.application_plugin import ApplicationPlugin

from .exceptions import PoePluginException

if TYPE_CHECKING:
    from cleo.events.console_command_event import ConsoleCommandEvent
    from cleo.events.event_dispatcher import EventDispatcher
    from cleo.io.io import IO

    from .config import PoeConfig


class PoeCommand(Command):
    prefix: str
    command_prefix: str = "poe"
    poe_config: PoeConfig

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
        poe = self.get_poe(self.application, self.io)
        task_status = poe(cli_args=self._get_argv())

        if task_status:
            raise SystemExit(task_status)

    @classmethod
    def get_poe(
        cls, application: Application, io: IO, poe_config: PoeConfig | None = None
    ):
        from .app import PoeThePoet

        try:
            from poetry.utils.env import EnvManager

            poetry_env_path = EnvManager(application.poetry).get().path
        except:  # noqa: E722
            poetry_env_path = None

        poe_config = poe_config or cls.poe_config

        poe = PoeThePoet(
            config=poe_config,
            output=io.output.stream,
            poetry_env_path=poetry_env_path,
            program_name=f"poetry {cls.command_prefix}",
            # Suppress global CLI options on poe that don't work as a poetry plugin
            suppress_args=(
                "help",
                "version",
                "verbosity",
                "project_root",
                "legacy_project_root",
                "ansi",
            ),
        )

        if io.output.is_quiet():
            poe.modify_verbosity(-1)
        elif io.is_verbose():
            poe.modify_verbosity(1)
        elif io.is_very_verbose():
            poe.modify_verbosity(2)

        return poe


class PoetryPlugin(ApplicationPlugin):
    def activate(self, application: Application) -> None:
        try:
            return self._activate(application)

        except:  # noqa: E722
            import os
            import sys

            debug = bool(int(os.environ.get("DEBUG_POE_PLUGIN", "0")))
            print(
                "error: poethepoet plugin encountered an error."
                + ("" if debug else " Set DEBUG_POE_PLUGIN=1 for details."),
                file=sys.stderr,
            )
            if debug:
                import traceback

                traceback.print_exc()
                raise SystemExit(1)

    def _activate(self, application: Application) -> None:
        try:
            poe_config = self._get_config(application)
        except RuntimeError:
            # If there's no pyproject.toml then probably that's OK, don't freak out
            return

        command_prefix = poe_config._project_config.get("poetry_command").strip()
        PoeCommand.command_prefix = command_prefix

        poe_tasks = poe_config.tasks
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
                if task_name.startswith("_"):
                    continue
                self._register_command(application, poe_config, task_name, task)
        else:
            self._register_command(
                application,
                poe_config,
                "",
                {"help": "Run poe tasks defined for this project"},
                command_prefix,
            )
            for task_name, task in poe_tasks.items():
                if task_name.startswith("_"):
                    continue
                self._register_command(
                    application, poe_config, task_name, task, f"{command_prefix} "
                )

        self._monkey_patch_cleo(command_prefix, list(poe_tasks.keys()))

        self._register_command_event_handler(
            application, poe_config._project_config.get("poetry_hooks", {}), poe_config
        )

    @classmethod
    def _get_config(cls, application: Application) -> PoeConfig:
        from .config import PoeConfig

        # Try respect poetry's '--directory' if set
        try:
            pyproject_dir = application.poetry.pyproject_path.parent
        except AttributeError:
            pyproject_dir = None

        poe_config = PoeConfig(cwd=pyproject_dir)
        poe_config.load_sync(strict=False)
        return poe_config

    def _validate_command_prefix(self, command_prefix: str):
        if command_prefix and not command_prefix.isalnum():
            raise PoePluginException(
                "Provided value in pyproject.toml for tool.poe.poetry_command "
                f"{command_prefix!r} is invalid. Only alphanumeric values are allowed."
            )

    def _register_command(
        self,
        application: Application,
        poe_config: PoeConfig,
        task_name: str,
        task: Any,
        prefix: str = "",
    ):
        command_name = prefix + task_name
        task_help = task.get("help", "") if isinstance(task, dict) else ""
        application.command_loader.register_factory(
            command_name,
            type(
                (task_name or prefix).replace("-", "").capitalize() + "Command",
                (PoeCommand,),
                {
                    "name": command_name,
                    "description": task_help,
                    "prefix": prefix,
                    "poe_config": poe_config,
                },
            ),
        )

    def _register_command_event_handler(
        self, application: Application, hooks: dict[str, str], poe_config: PoeConfig
    ):
        if not hooks:
            return

        pre_hooks = {}
        post_hooks = {}
        for key, task_ref in hooks.items():
            prefix, command = key.split("_", 1)
            command = command.replace("_", " ")
            if prefix == "pre":
                pre_hooks[command] = task_ref
            if prefix == "post":
                post_hooks[command] = task_ref

        if pre_hooks:
            application.event_dispatcher.add_listener(
                COMMAND,
                self._get_command_event_handler(pre_hooks, application, poe_config),
            )
        if post_hooks:
            application.event_dispatcher.add_listener(
                TERMINATE,
                self._get_command_event_handler(post_hooks, application, poe_config),
            )

    def _get_command_event_handler(
        self, hooks: dict[str, str], application: Application, poe_config: PoeConfig
    ):
        def command_event_handler(
            event: ConsoleCommandEvent,
            event_name: str,
            dispatcher: EventDispatcher,
        ) -> None:
            task = hooks.get(event.command.name)
            if not task:
                return

            import shlex

            task_status = PoeCommand.get_poe(application, event.io, poe_config)(
                cli_args=shlex.split(task), internal=True
            )

            if task_status:
                event.io.write_line(
                    "<error>Cancelling command due to failed hook task</error>"
                )
                raise SystemExit(task_status)

        return command_event_handler

    def _monkey_patch_cleo(self, prefix: str, task_names: list[str]):
        """
        Cleo is quite opinionated about CLI structure and loose about how options are
        used, and so doesn't currently support individual commands having their own way
        of interpreting arguments, and forces them to inherit certain options from the
        application. This is a problem for poe which requires that global options are
        provided before the task name, and everything after the task name is interpreted
        ONLY in terms of the task.

        This hack monkey-patches internals of Cleo that are invoked directly after
        plugin's are loaded by poetry, and exploits a feature whereby argument and
        option parsing are effectively disabled following any occurrence of a "--" on
        the command line, but parsing of the command name still works! Thus the solution
        is to detect when it is a command from this plugin that is about to be executed
        and insert the "--" token at the start of the tokens list of the ArgvInput
        instance that the application is about to read the CLI options from.

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

            return continue_run(self, io)

        # Apply the patch
        cleo.application.Application._run = _run


def _index_of_first_non_option(tokens: list[str]):
    """
    Find the index of the first token that doesn't start with `-`, and isn't directly
    preceded by either `--project` or `--directory`.

    Returns len(tokens) if none is found.
    """

    options_with_args = ("--project", "--directory")
    previous_token = ""
    for index, token in enumerate(tokens):
        if token[0] != "-" and previous_token not in options_with_args:
            return index
        previous_token = token

    return len(tokens)
