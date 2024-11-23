from .__version__ import __version__

__all__ = ["__version__", "main"]


def main():
    import sys
    from pathlib import Path

    if len(sys.argv) > 1 and sys.argv[1].startswith("_"):
        first_arg = sys.argv[1]  # built in task name
        second_arg = next(iter(sys.argv[2:]), "")  # config path or poe alias
        third_arg = next(iter(sys.argv[3:]), "")  # path to alias config for bash

        if first_arg in ("_list_tasks", "_describe_tasks"):
            target_path = (
                str(Path(second_arg).expanduser().resolve()) if second_arg else None
            )
            _list_tasks(target_path=target_path)
            return

        target_path = ""
        if second_arg:
            if not second_arg.isalnum():
                raise ValueError(f"Invalid alias: {second_arg!r}")

            if third_arg:
                if not Path(third_arg).expanduser().resolve().exists():
                    raise ValueError(f"Invalid path: {third_arg!r}")

                target_path = str(Path(third_arg).resolve())

        if first_arg == "_zsh_completion":
            from .completion.zsh import get_zsh_completion_script

            print(get_zsh_completion_script(name=second_arg))
            return

        if first_arg == "_bash_completion":
            from .completion.bash import get_bash_completion_script

            print(get_bash_completion_script(name=second_arg, target_path=target_path))
            return

        if first_arg == "_fish_completion":
            from .completion.fish import get_fish_completion_script

            print(get_fish_completion_script(name=second_arg))
            return

    from .app import PoeThePoet

    app = PoeThePoet(cwd=Path().resolve(), output=sys.stdout)
    result = app(cli_args=sys.argv[1:])
    if result:
        raise SystemExit(result)


def _list_tasks(target_path: str = ""):
    """
    A special task accessible via `poe _list_tasks` for use in shell completion

    Note this code path should include minimal imports to avoid slowing down the shell
    """

    try:
        from .config import PoeConfig

        config = PoeConfig()
        config.load(target_path, strict=False)
        task_names = (task for task in config.task_names if task and task[0] != "_")
        print(" ".join(task_names))
    except Exception:
        # this happens if there's no pyproject.toml present
        pass
