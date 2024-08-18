def get_bash_completion_script(name: str = "", target_path: str = "") -> str:
    """
    A special task accessible via `poe _bash_completion` that prints a basic bash
    completion script for the presently available poe tasks
    """

    # TODO: see if it's possible to support completion of global options anywhere as
    #       nicely as for zsh

    name = name or "poe"
    func_name = f"_{name}_complete"

    return "\n".join(
        (
            func_name + "() {",
            "    local cur",
            '    cur="${COMP_WORDS[COMP_CWORD]}"',
            f"    COMPREPLY=( $(compgen -W \"$(poe _list_tasks '{target_path}')\""
            + " -- ${cur}) )",
            "    return 0",
            "}",
            f"complete -o default -F {func_name} {name}",
        )
    )
