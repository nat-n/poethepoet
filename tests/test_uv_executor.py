import shutil

import pytest


@pytest.mark.skipif(not shutil.which("uv"), reason="No uv available")
def test_uv_package_script_task(run_poe_subproc, projects):
    result = run_poe_subproc("-q", "script-task", project="uv")

    assert result.capture == ""
    assert result.stderr == ""
    assert result.stdout == "Hello from uv-project 0.0.99\n"


@pytest.mark.skipif(not shutil.which("uv"), reason="No uv available")
def test_uv_executor_env(run_poe_subproc, projects, is_windows):
    result = run_poe_subproc("show-env", project="uv")

    assert result.capture == "Poe => poe_test_env\n"
    assert result.stderr == ""

    if is_windows:
        assert f"VIRTUAL_ENV={projects['uv']}\\.venv" in result.stdout
    else:
        assert f"VIRTUAL_ENV={projects['uv']}/.venv" in result.stdout
    assert "POE_ACTIVE=uv" in result.stdout


@pytest.mark.skipif(not shutil.which("uv"), reason="No uv available")
def test_uv_executor_task_with_cwd(
    run_poe_subproc, projects, poe_project_path, is_windows
):
    if is_windows:
        subproject_path = f"{projects['uv']}\\subproject"
        result = run_poe_subproc("-C", subproject_path, "test-cwd", "..\\..")
    else:
        subproject_path = f"{projects['uv']}/subproject"
        result = run_poe_subproc("-C", subproject_path, "test-cwd", "../..")

    assert result.capture == (
        "Poe => echo UV_RUN_RECURSION_DEPTH: $UV_RUN_RECURSION_DEPTH\n"
        "echo VIRTUAL_ENV: $VIRTUAL_ENV\n"
        "echo pwd: $(pwd)\n"
    )

    if is_windows:
        assert f"VIRTUAL_ENV: {subproject_path}\\.venv" in result.stdout
    else:
        assert f"VIRTUAL_ENV: {subproject_path}/.venv" in result.stdout
        assert f"pwd: {poe_project_path}/tests/fixtures\n" in result.stdout
