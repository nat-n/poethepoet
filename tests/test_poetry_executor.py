import shutil

import pytest


@pytest.mark.skipif(not shutil.which("poetry"), reason="No poetry available")
def test_poetry_executor_with_task_run_options(run_poe_subproc, projects):
    """Test that task-level executor_run_options are passed to poetry run"""
    result = run_poe_subproc("test-poetry-run-options", project="example")

    assert result.code == 0
    assert "poetry run options test" in result.stdout
