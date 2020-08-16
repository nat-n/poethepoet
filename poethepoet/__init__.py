from .__version__ import __version__


def main():
    import sys

    if len(sys.argv) == 2 and sys.argv[1].startswith("_"):
        if sys.argv[1] == "_describe_tasks":
            _describe_tasks()
            return
        if sys.argv[1] == "_zsh_completion":
            _zsh_completion()
            return

    from pathlib import Path
    from .app import PoeThePoet

    app = PoeThePoet(cwd=Path(".").resolve(), output=sys.stdout)
    result = app(cli_args=sys.argv[1:])
    if result:
        raise SystemExit(result)


def _describe_tasks():
    """
    A special task accessible via `poe _describe_tasks` for use in shell completion

    Note this code path should include minimal imports to avoid slowing down the shell
    """

    try:
        from .config import PoeConfig

        config = PoeConfig()
        config.load()
        task_names = (task for task in config.tasks.keys() if task and task[0] != "_")
        print(" ".join(task_names))
    except Exception:  # pylint: disable=broad-except
        # this happens if there's no pyproject.toml present
        pass


def _zsh_completion():
    """
    A special task accessible via `poe _zsh_completion` that prints a zsh completion
    script for poe generated from the argparses config
    """
    from pathlib import Path
    from .app import PoeThePoet

    # build and interogate the argument parser as the normal cli would
    app = PoeThePoet(cwd=Path(".").resolve())
    parser = app.ui.build_parser()
    global_options = parser._action_groups[1]._group_actions
    excl_groups = [
        set(excl_group._group_actions)
        for excl_group in parser._mutually_exclusive_groups
    ]

    def format_exclusions(excl_option_strings):
        return f"($ALL_EXLC {' '.join(sorted(excl_option_strings))})"

    # format the zsh completion script
    args_lines = ["    _arguments -C"]
    for option in global_options:
        # help and version are special cases that dont go with other args
        if option.dest in ["help", "version"]:
            options_part = (
                option.option_strings[0]
                if len(option.option_strings) == 1
                else '"{' + ",".join(sorted(option.option_strings)) + '}"'
            )
            args_lines.append(f'"(- *){options_part}[{option.help}]"')
            continue

        # collect other options that are exclusive to this one
        excl_options = next(
            (
                excl_group - {option}
                for excl_group in excl_groups
                if option in excl_group
            ),
            tuple(),
        )
        # collect all option strings that are exclusive with this one
        excl_option_strings = set(
            [
                option_string
                for excl_option in excl_options
                for option_string in excl_option.option_strings
            ]
        ) | set(option.option_strings)

        if len(excl_option_strings) == 1:
            options_part = option.option_strings[0]
        elif len(option.option_strings) == 1:
            options_part = (
                format_exclusions(excl_option_strings) + option.option_strings[0]
            )
        else:
            options_part = (
                format_exclusions(excl_option_strings)
                + '"{'
                + ",".join(sorted(option.option_strings))
                + '}"'
            )

        args_lines.append(f'"{options_part}[{option.help}]"')

    args_lines.append('"1: :($TASKS)"')
    args_lines.append('"*::arg:->args"')

    print(
        "\n".join(
            [
                "#compdef _poe poe\n",
                "function _poe {",
                '    local ALL_EXLC=("-h" "--help" "--version")',
                "    local TASKS=($(poe _describe_tasks))",
                "",
                " \\\n        ".join(args_lines),
                "",
                # Only offer filesystem based autocompletions after a task is specified
                "    if (($TASKS[(Ie)$line[1]])); then",
                "        _files",
                "    fi",
                "}",
            ]
        )
    )
