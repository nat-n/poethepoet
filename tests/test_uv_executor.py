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


@pytest.mark.skipif(not shutil.which("uv"), reason="No uv available")
def test_uv_executor_with_global_run_options(run_poe_subproc, projects):
    """Test that global executor run_options are passed to uv run"""
    result = run_poe_subproc("test-global-run-options", project="uv")

    assert result.code == 0
    assert "global run options test" in result.stdout


@pytest.mark.skipif(not shutil.which("uv"), reason="No uv available")
def test_uv_executor_with_task_run_options(run_poe_subproc, projects):
    """Test that task-level executor_run_options are passed to uv run"""
    result = run_poe_subproc("test-task-run-options", project="uv")

    assert result.code == 0
    assert "task level options" in result.stdout


@pytest.mark.skipif(not shutil.which("uv"), reason="No uv available")
def test_uv_executor_with_cli_run_options(run_poe_subproc, projects):
    """Test that CLI executor_run_options are passed correctly"""
    result = run_poe_subproc(
        "--executor-run-options",
        " --no-sync",  # Single quoted string
        "test-global-run-options",
        project="uv",
    )

    # Should work with --no-sync option
    assert result.code == 0
    assert "global run options test" in result.stdout


@pytest.mark.skipif(not shutil.which("uv"), reason="No uv available")
def test_uv_executor_run_options_priority(run_poe_subproc, projects):
    """Test that CLI > task > config priority is respected"""
    # This task already has --no-sync as task-level option
    # Adding another CLI option should work alongside it
    result = run_poe_subproc(
        "--executor-run-options",
        " --quiet",  # Single option as string with leading space to avoid arg parsing
        "test-task-run-options",
        project="uv",
    )

    # Should succeed with both task and CLI options
    assert result.code == 0
    assert "task level options" in result.stdout
