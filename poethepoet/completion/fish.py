def get_fish_completion_script(name: str = "") -> str:
    """
    A special task accessible via `poe _fish_completion` that prints a basic fish
    completion script for the presently available poe tasks
    """

    # TODO: work out how to:
    # - support completion of global options (with help) only if no task provided
    #   without having to call poe for every option which would be too slow
    # - include task help in (dynamic) task completions

    name = name or "poe"
    func_name = f"__list_{name}_tasks"

    return "\n".join(
        (
            "function " + func_name,
            "    # Check if `-C target_path` have been provided",
            "    set target_path ''",
            "    set prev_args (commandline -pco)",
            "    for i in (seq (math (count $prev_args) - 1))",
            "        set j (math $i + 1)",
            "        set k (math $i + 2)",
            '        if test "$prev_args[$j]" = "-C" && test "$prev_args[$k]" != ""',
            '            set target_path "$prev_args[$k]"',
            "            break",
            "        end",
            "    end",
            "    set tasks (poe _list_tasks $target_path | string split ' ')",
            "    set arg (commandline -ct)",
            "    for task in $tasks",
            f'        if test "$task" != {name} && contains $task $prev_args',
            # TODO: offer $task specific options
            '            complete -C "ls $arg"',
            "            return 0",
            "        end",
            "    end",
            "    for task in $tasks",
            "        echo $task",
            "    end",
            "end",
            f"complete -c {name} --no-files -a '({func_name})'",
        )
    )
