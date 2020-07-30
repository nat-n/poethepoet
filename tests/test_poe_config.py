import os
from pathlib import Path
import tempfile
import toml


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
