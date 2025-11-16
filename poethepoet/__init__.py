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
    app = PoeThePoet(cwd=Path().resolve(), output=io)
    result = app(cli_args=sys.argv[1:])
    if result:
        raise SystemExit(result)


def _run_builtin_task(
    task_name: str, second_arg: str = "", third_arg: str = ""
) -> bool:
    """
    Run a special builtin task for shell completion purposes.

    task_name: The name of the builtin task to run, e.g. "_list_tasks"
    second_arg: config path or poe alias (depending on the task)
    third_arg: path to alias config for bash completion

    returns True if the task was handled, False otherwise
    """

    if task_name in ("_list_tasks", "_describe_tasks"):
        target_path = (
            str(Path(second_arg).expanduser().resolve()) if second_arg else None
        )
        _list_tasks(target_path=target_path)
        return True

    target_path = ""
    if second_arg:
        if not second_arg.isalnum():
            raise ValueError(f"Invalid alias: {second_arg!r}")

        if third_arg:
            if not Path(third_arg).expanduser().resolve().exists():
                raise ValueError(f"Invalid path: {third_arg!r}")

            target_path = str(Path(third_arg).resolve())

    if task_name == "_zsh_completion":
        from .completion.zsh import get_zsh_completion_script

        print(get_zsh_completion_script(name=second_arg))
        return True

    if task_name == "_bash_completion":
        from .completion.bash import get_bash_completion_script

        print(get_bash_completion_script(name=second_arg, target_path=target_path))
        return True

    if task_name == "_fish_completion":
        from .completion.fish import get_fish_completion_script

        print(get_fish_completion_script(name=second_arg))
        return True

    return False


def _list_tasks(target_path: str | None = None):
    """
    A special task accessible via `poe _list_tasks` for use in shell completion

    Note this code path should include minimal imports to avoid slowing down the shell
    """

    try:
        from .config import PoeConfig

        config = PoeConfig()
        config.load_sync(target_path, strict=False)
        task_names = (task for task in config.task_names if task and task[0] != "_")
        print(" ".join(task_names))
    except Exception:
        # this happens if there's no pyproject.toml present
        pass
