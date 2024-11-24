import pytest


@pytest.fixture
def generate_pyproject(temp_pyproject):
    def generator(lvl1_ignore_fail=False, lvl2_ignore_fail=False):
        def fmt_ignore_fail(value):
            if value is True:
                return "ignore_fail = true"
            elif isinstance(value, str):
                return f'ignore_fail = "{value}"'
            else:
                return ""

        project_tmpl = f"""
            [tool.poe.tasks]
            task_0 = "echo 'task 0 success'"
            task_1.shell = "echo 'task 1 error'; exit 1;"
            task_2.shell = "echo 'task 2 error'; exit 1;"
            task_3.shell = "echo 'task 3 success'; exit 0;"

            [tool.poe.tasks.lvl1_seq]
            sequence = ["task_1", "task_2", "task_3"]
            {fmt_ignore_fail(lvl1_ignore_fail)}

            [tool.poe.tasks.lvl2_seq]
            sequence = ["task_0", "lvl1_seq", "task_3"]
            {fmt_ignore_fail(lvl2_ignore_fail)}
        """

        return temp_pyproject(project_tmpl)

    return generator


@pytest.mark.parametrize("fail_value", [True, "return_zero"])
def test_full_ignore(generate_pyproject, run_poe, fail_value):
    project_path = generate_pyproject(lvl1_ignore_fail=fail_value)
    result = run_poe("lvl1_seq", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert "task 1 error" in result.capture, "Expected first task in log"
    assert "task 2 error" in result.capture, "Expected second task in log"
    assert "task 3 success" in result.capture, "Expected third task in log"


def test_without_ignore(generate_pyproject, run_poe):
    project_path = generate_pyproject(lvl1_ignore_fail=False)
    result = run_poe("lvl1_seq", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "task 1 error" in result.capture, "Expected first task in log"
    assert "task 2 error" not in result.capture, "Second task shouldn't run"
    assert "task 3 success" not in result.capture, "Third task shouldn't run"
    assert "Sequence aborted after failed subtask 'task_1'" in result.capture


def test_return_non_zero(generate_pyproject, run_poe):
    project_path = generate_pyproject(lvl1_ignore_fail="return_non_zero")
    result = run_poe("lvl1_seq", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "task 1 error" in result.capture, "Expected first task in log"
    assert "task 2 error" in result.capture, "Expected second task in log"
    assert "task 3 success" in result.capture, "Expected third task in log"
    assert "Subtasks 'task_1', 'task_2' returned non-zero exit status" in result.capture


def test_invalid_ignore_value(generate_pyproject, run_poe):
    project_path = generate_pyproject(lvl1_ignore_fail="invalid_value")
    result = run_poe("lvl1_seq", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert (
        "| Option 'ignore_fail' must be one of "
        "(True, False, 'return_zero', 'return_non_zero')\n"
    ) in result.capture


def test_nested_without_ignore(generate_pyproject, run_poe):
    project_path = generate_pyproject()
    result = run_poe("lvl2_seq", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "task 0 success" in result.capture, "Expected zeroth task in log"
    assert "task 1 error" in result.capture, "Expected first task in log"
    assert "task 2 error" not in result.capture, "Second task shouldn't run"
    assert "task 3 success" not in result.capture, "Third task shouldn't run"
    assert "Sequence aborted after failed subtask 'task_1'" in result.capture


def test_nested_lvl1_return_non_zero(generate_pyproject, run_poe):
    project_path = generate_pyproject(lvl1_ignore_fail="return_non_zero")
    result = run_poe("lvl2_seq", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "task 1 error" in result.capture, "Expected first task in log"
    assert "task 2 error" in result.capture, "Expected second task in log"
    assert "task 3 success" in result.capture, "Expected third task in log"
    assert "Subtasks 'task_1', 'task_2' returned non-zero exit status" in result.capture


def test_nested_lvl2_return_non_zero(generate_pyproject, run_poe):
    project_path = generate_pyproject(lvl2_ignore_fail="return_non_zero")
    result = run_poe("lvl2_seq", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "task 1 error" in result.capture, "Expected first task in log"
    assert "task 2 error" not in result.capture, "Expected task 2 to be skipped"
    assert "task 3 success" in result.capture, "Expected third task in log"
    assert (
        "Warning: Sequence aborted after failed subtask 'task_1'" in result.stdout
    )  # TODO log warnings to capture
    assert "Error: Subtask 'lvl1_seq' returned non-zero exit status" in result.capture


def test_nested_both_return_non_zero(generate_pyproject, run_poe):
    project_path = generate_pyproject(
        lvl1_ignore_fail="return_non_zero", lvl2_ignore_fail="return_non_zero"
    )
    result = run_poe("lvl2_seq", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "task 1 error" in result.capture, "Expected first task in log"
    assert "task 2 error" in result.capture, "Expected second task in log"
    assert "task 3 success" in result.capture, "Expected third task in log"
    assert (
        "Warning: Subtasks 'task_1', 'task_2' returned non-zero exit status"
        in result.stdout
    )  # TODO log warnings to capture
    assert (
        "Error: Subtask 'lvl1_seq' returned non-zero exit status" in result.capture
    )  # TODO log warnings to capture
