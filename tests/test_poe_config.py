import os
from pathlib import Path
import tempfile


def test_setting_default_task_type(run_poe_subproc, scripts_project_path, esc_prefix):
    result = run_poe_subproc(
        "greet",
        "nat,",
        r"welcome to " + esc_prefix + "${POE_ROOT}",
        cwd=scripts_project_path,
    )
    assert result.capture == f"Poe => greet nat, welcome to {scripts_project_path}\n"
    assert result.stdout == f"hello nat, welcome to {scripts_project_path}\n"
    assert result.stderr == ""


def test_setting_default_array_item_task_type(run_poe_subproc, scripts_project_path):
    result = run_poe_subproc("composite_task", cwd=scripts_project_path,)
    assert result.capture == f"Poe => echo Hello\nPoe => echo World!\n"
    assert result.stdout == f"Hello\nWorld!\n"
    assert result.stderr == ""


def test_setting_global_env_vars(run_poe_subproc, is_windows):
    result = run_poe_subproc("travel")
    if is_windows:
        assert result.capture == f"Poe => echo 'from EARTH to'\nPoe => travel[1]\n"
        assert result.stdout == f"'from EARTH to'\nMARS\n"
    else:
        assert result.capture == f"Poe => echo from EARTH to\nPoe => travel[1]\n"
        assert result.stdout == f"from EARTH to\nMARS\n"
    assert result.stderr == ""
