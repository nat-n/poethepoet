from __future__ import annotations

from pathlib import Path

from .__version__ import __version__

__all__ = ["__version__", "main"]


def main():
    import sys

    if (
        len(sys.argv) > 1
        and sys.argv[1].startswith("_")
        and _run_builtin_task(*sys.argv[1:4])
    ):
        return

    from .app import PoeThePoet
    from .io import PoeIO

    io = PoeIO(output=sys.stdout, error=sys.stderr, make_default=True)
    app = PoeThePoet(cwd=Path.cwd(), output=io)
    result = app(cli_args=sys.argv[1:])
    if result:
        raise SystemExit(result)


def iter_tasks(target_path: str = "."):
    from .config import PoeConfig

    config = PoeConfig()
    config.load_sync(target_path, strict=False)
    for task in config.task_names:
        if task and task[0] != "_":
            yield task


def _run_builtin_task(
    task_name: str, second_arg: str = "", third_arg: str = ""
) -> bool:
    """
    Run a special builtin task.

    task_name: The name of the builtin task to run, e.g. "_list_tasks"
    second_arg: config path, poe alias, or target directory (depending on the task)
    third_arg: path to alias config for bash completion

    returns True if the task was handled, False otherwise
    """

    if task_name in ("_list_tasks", "_describe_tasks"):
        target_path = (
            str(Path(second_arg).expanduser().resolve()) if second_arg else None
        )
        _list_tasks(target_path=target_path)
        return True

    if task_name == "_zsh_describe_tasks":
        target_path = (
            str(Path(second_arg).expanduser().resolve()) if second_arg else None
        )
        _zsh_describe_tasks(target_path=target_path)
        return True

    if task_name == "_describe_task_args":
        # second_arg is task name, third_arg is optional target path
        if second_arg:
            target_path = (
                str(Path(third_arg).expanduser().resolve()) if third_arg else None
            )
            _describe_task_args(task_name=second_arg, target_path=target_path)
        return True

    if task_name == "_install_skill":
        import sys

        from .skills.install import install_skill

        skill_args = sys.argv[2:]
        upgrade = "--upgrade" in skill_args
        positional = [a for a in skill_args if not a.startswith("--")]
        skills_dir = Path(positional[0]) if positional else None
        install_skill(skills_dir=skills_dir, upgrade=upgrade)
        return True

    if task_name not in (
        "_zsh_completion",
        "_bash_completion",
        "_fish_completion",
        "_powershell_completion",
    ):
        # Not a builtin, so let the app handle it like any other task name
        return False

    if second_arg and not _is_valid_alias(second_arg):
        _exit_with_error(
            f"Invalid alias name {second_arg!r} for shell completion. "
            "Alias names may only contain letters, digits, '_', '-' and '.'"
        )

    if task_name == "_zsh_completion":
        from .completion.zsh import get_zsh_completion_script

        print(get_zsh_completion_script(name=second_arg))
        return True

    if task_name == "_bash_completion":
        from .completion.bash import get_bash_completion_script

        if third_arg and not Path(third_arg).expanduser().resolve().exists():
            _exit_with_error(f"Invalid path {third_arg!r} for shell completion")

        print(get_bash_completion_script(name=second_arg))
        return True

    if task_name == "_fish_completion":
        from .completion.fish import get_fish_completion_script

        print(get_fish_completion_script(name=second_arg))
        return True

    if task_name == "_powershell_completion":
        from .completion.powershell import get_powershell_completion_script

        print(get_powershell_completion_script(name=second_arg))
        return True

    return False


def _is_valid_alias(name: str) -> bool:
    """
    Check that a command alias is safe to embed in a shell completion script.
    """
    return name[0] != "-" and all(
        char.isascii() and (char.isalnum() or char in "_-.") for char in name
    )


def _exit_with_error(message: str):
    """
    Print an error for a misused builtin task and exit with a non-zero code.
    """
    import sys

    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def _format_help(text: str | None, max_len: int = 60) -> str:
    """
    Format help text for shell completion output.

    - Takes first line only
    - Truncates with ellipsis if too long
    - Escapes special characters (backslash, colon, tab)
    """
    if not text:
        return " "  # Space placeholder - empty descriptions can confuse _describe
    # First line only, strip whitespace
    text = text.split("\n")[0].strip()

    # Truncate with ellipsis if too long
    if len(text) > max_len:
        text = text[: max_len - 3].rstrip() + "..."

    # Escape special characters for
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("\t", " ")


def _escape_choice(value: str) -> str:
    """
    Escape a choice value for shell completion output.

    Quotes the value with single quotes if it contains special characters
    (spaces, tabs, newlines, quotes, backslash, $, backtick).
    Single quotes within the value are escaped as '\\'' (end quote, escaped
    quote, start quote).
    """
    if not value:
        return value
    # Characters that require quoting
    if any(c in value for c in " \t\n\"'\\$`"):
        # Escape single quotes: end quote, add escaped quote, start new quote
        escaped = value.replace("'", "'\\''")
        return f"'{escaped}'"
    return value


def _list_tasks(target_path: str | None = None):
    """
    A special task accessible via `poe _list_tasks` for use in shell completion

    Note this code path should include minimal imports to avoid slowing down the shell
    """
    try:  # noqa: SIM105
        print(" ".join(iter_tasks(target_path or "")))
    except Exception:
        # this happens if there's no pyproject.toml present
        pass


def _zsh_describe_tasks(target_path: str | None = None):
    """
    Output task names with descriptions in zsh _describe format.

    Format: one task per line as "name:description"
    - Colons in task names and descriptions are escaped as \\:
    - Descriptions truncated to 60 chars with ...
    - Tasks without help get empty description (name:)
    """
    try:
        from .config import PoeConfig

        config = PoeConfig()
        config.load_sync(target_path, strict=False)

        for task_name in config.task_names:
            if not task_name or task_name.startswith("_"):
                continue

            task = config.lookup_task(task_name)
            task_def = task.task_def if task else {}

            # Extract help text - handle both dict and simple string task definitions
            if isinstance(task_def, dict):
                help_text = task_def.get("help", "") or ""
            else:
                help_text = ""

            help_text = _format_help(help_text)
            # _describe splits on the first unescaped colon, so namespaced task
            # names (e.g. "db:migrate") must have their colons escaped too
            escaped_name = task_name.replace(":", "\\:")
            print(f"{escaped_name}:{help_text}")

    except Exception:
        # this happens if there's no pyproject.toml present
        pass


def _describe_task_args(task_name: str, target_path: str | None = None):
    """
    Output argument specs for a specific task in a shell-agnostic format.

    Used by both bash and zsh completion scripts.

    Format: tab-separated fields per line:
        <options>   <type>  <help>  <choices>

    Where:
    - options: comma-separated option strings (e.g., "--greeting,-g")
    - type: "boolean", "string", "integer", "float", or "positional"
    - help: description text (colons escaped as \\:)
    - choices: space-separated list of allowed values ("_" if no choices)

    Example output:
        --greeting,-g   string  The greeting to use     _
        --verbose,-v    boolean Verbose mode            _
        --flavor,-f     string  Flavor                  vanilla chocolate strawberry
        name    positional  The name argument           _
    """
    try:
        from .config import PoeConfig
        from .task.args import ArgSpec

        config = PoeConfig()
        config.load_sync(target_path, strict=False)

        task = config.lookup_task(task_name)
        if not task:
            return
        task_def = task.task_def
        if not isinstance(task_def, dict):
            return

        args_def = task_def.get("args")
        if not args_def:
            return

        for arg in ArgSpec.normalize(args_def, strict=False):
            help_text = _format_help(arg.get("help"))

            # Format choices as space-separated values with proper escaping
            # Use "_" as placeholder for empty (shell read may skip consecutive tabs)
            choices_list = [
                _escape_choice(str_choice)
                for choice in (arg.get("choices") or [])
                if (str_choice := str(choice))
            ]
            choices = " ".join(choices_list) if choices_list else "_"

            arg_details: list[str] = []

            if arg.get("positional"):
                if name := arg.get("name", ""):
                    arg_details = [name, "positional", help_text, choices]
            else:
                # Join all option strings for this arg
                arg_details = [
                    ",".join(arg.get("options")),
                    arg.get("type", "string"),
                    help_text,
                    choices,
                ]

            if arg_details:
                print("\t".join(arg_details))

    except Exception:
        # Silently fail - no completions is better than breaking the shell
        pass
