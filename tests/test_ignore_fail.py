import pytest


@pytest.fixture()
def generate_pyproject(temp_pyproject):
    """Return function which generates pyproject.toml with a given ignore_fail value."""

    def generator(ignore_fail):
        project_tmpl = """
            [tool.poe.tasks]
            task_1 = { shell = "echo 'task 1 error'; exit 1;" }
            task_2 = { shell = "echo 'task 2 error'; exit 1;" }
            task_3 = { shell = "echo 'task 3 success'; exit 0;" }

            [tool.poe.tasks.all_tasks]
            sequence = ["task_1", "task_2", "task_3"]
        """
        if isinstance(ignore_fail, bool) and ignore_fail:
            project_tmpl += "\nignore_fail = true"
        elif not isinstance(ignore_fail, bool):
            project_tmpl += f'\nignore_fail = "{ignore_fail}"'

        return temp_pyproject(project_tmpl)

    return generator


@pytest.mark.parametrize("fail_value", [True, "return_zero"])
def test_full_ignore(generate_pyproject, run_poe, fail_value):
    project_path = generate_pyproject(ignore_fail=fail_value)
    result = run_poe("all_tasks", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert "task 1 error" in result.capture, "Expected first task in log"
    assert "task 2 error" in result.capture, "Expected second task in log"
    assert "task 3 success" in result.capture, "Expected third task in log"


def test_without_ignore(generate_pyproject, run_poe):
    project_path = generate_pyproject(ignore_fail=False)
    result = run_poe("all_tasks", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "task 1 error" in result.capture, "Expected first task in log"
    assert "task 2 error" not in result.capture, "Second task shouldn't run"
    assert "task 3 success" not in result.capture, "Third task shouldn't run"
    assert "Sequence aborted after failed subtask 'task_1'" in result.capture


def test_return_non_zero(generate_pyproject, run_poe):
    project_path = generate_pyproject(ignore_fail="return_non_zero")
    result = run_poe("all_tasks", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "task 1 error" in result.capture, "Expected first task in log"
    assert "task 2 error" in result.capture, "Expected second task in log"
    assert "task 3 success" in result.capture, "Expected third task in log"
    assert "Subtasks task_1, task_2 returned non-zero exit status" in result.capture


def test_invalid_ingore_value(generate_pyproject, run_poe):
    project_path = generate_pyproject(ignore_fail="invalid_value")
    result = run_poe("all_tasks", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert (
        "| Option 'ignore_fail' must be one of "
        "(True, False, 'return_zero', 'return_non_zero')\n"
    ) in result.capture
