from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable


def get_zsh_completion_script(name: str = "") -> str:
    """
    A special task accessible via `poe _zsh_completion` that prints a zsh completion
    script for poe generated from the argparses config
    """
    from pathlib import Path

    from ..app import PoeThePoet

    name = name or "poe"

    # build and interogate the argument parser as the normal cli would
    app = PoeThePoet(cwd=Path().resolve())
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
        if option.help == "==SUPPRESS==":
            continue

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
        excl_options: Iterable[Any] = next(
            (
                excl_group - {option}
                for excl_group in excl_groups
                if option in excl_group
            ),
            tuple(),
        )
        # collect all option strings that are exclusive with this one
        excl_option_strings: set[str] = {
            option_string
            for excl_option in excl_options
            for option_string in excl_option.option_strings
        } | set(option.option_strings)

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

    args_lines.append('"1: :($tasks)"')
    args_lines.append('": :($tasks)"')  # needed to complete task after global options
    args_lines.append('"*::arg:->args"')

    target_path_logic = """
    local DIR_ARGS=("-C" "--directory" "--root")

    local target_path=""
    local tasks=()

    for ((i=2; i<${#words[@]}; i++)); do
        # iter arguments passed so far
        if (( $DIR_ARGS[(Ie)${words[i]}] )); then
            # arg is one of DIR_ARGS, so the next arg should be the target_path
            if (( ($i+1) >= ${#words[@]} )); then
                # this is the last arg, the next one should be path
                _files
                return
            fi
            target_path="${words[i+1]}"
            tasks=($(poe _list_tasks $target_path))
            i=$i+1
        elif [[ "${words[i]}" != -* ]] then
            if (( ${#tasks[@]}<1 )); then
                # get the list of tasks if we didn't already
                tasks=($(poe _list_tasks $target_path))
            fi
            if (( $tasks[(Ie)${words[i]}] )); then
                # a task has been given so complete with files
                _files
                return
            fi
        fi
    done

    if (( ${#tasks[@]}<1 )); then
        # get the list of tasks if we didn't already
        tasks=($(poe _list_tasks $target_path))
    fi
    """

    return "\n".join(
        [
            f"#compdef _{name} {name}\n",
            f"function _{name} {{",
            target_path_logic,
            '    local ALL_EXLC=("-h" "--help" "--version")',
            "",
            " \\\n        ".join(args_lines),
            "",
            # Only offer filesystem based autocompletions after a task is specified
            "    if (($tasks[(Ie)$line[1]])); then",
            "        _files",
            "    fi",
            "}",
        ]
    )
