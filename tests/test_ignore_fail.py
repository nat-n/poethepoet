import pytest


def fmt_ignore_fail(value):
    if value is True:
        return "ignore_fail = true"
    if isinstance(value, str):
        return f'ignore_fail = "{value}"'
    if isinstance(value, list):
        return f"ignore_fail = {value}"
    return ""


EXEC_TASK_CASES = (
    ("cmd", "cmd_fail_1", "poe_test_fail 0 1", 1),
    ("shell", "shell_fail_1", "sys.exit(1)", 1),
    ("expr", "expr_fail_1", "Poe => False", 1),
    ("script", "script_fail_1", "Poe => script_fail_1", 1),
)
EXEC_TASK_FAIL_2_CASES = (
    ("cmd", "cmd_fail_2", "poe_test_fail 0 2", 2),
    ("shell", "shell_fail_2", "sys.exit(2)", 2),
    ("expr", "expr_fail_2", "Poe => False", 2),
    ("script", "script_fail_2", "Poe => script_fail_2", 2),
)
EXEC_TASK_IDS = [case[0] for case in EXEC_TASK_CASES]


@pytest.fixture
def generate_pyproject(temp_pyproject):
    def generator(lvl1_ignore_fail=False, lvl2_ignore_fail=False):
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


@pytest.fixture
def generate_exec_pyproject(temp_pyproject):
    def generator(ignore_fail_overrides=None):
        ignore_fail_overrides = ignore_fail_overrides or {}

        def task_ignore(task_name):
            return fmt_ignore_fail(ignore_fail_overrides.get(task_name))

        project_tmpl = f"""
            [tool.poe.tasks.cmd_fail_1]
            cmd = "poe_test_fail 0 1"
            {task_ignore("cmd_fail_1")}

            [tool.poe.tasks.cmd_fail_2]
            cmd = "poe_test_fail 0 2"
            {task_ignore("cmd_fail_2")}

            [tool.poe.tasks.shell_fail_1]
            interpreter = "python"
            shell = "import sys; sys.exit(1)"
            {task_ignore("shell_fail_1")}

            [tool.poe.tasks.shell_fail_2]
            interpreter = "python"
            shell = "import sys; sys.exit(2)"
            {task_ignore("shell_fail_2")}

            [tool.poe.tasks.expr_fail_1]
            expr = "False"
            assert = 1
            {task_ignore("expr_fail_1")}

            [tool.poe.tasks.expr_fail_2]
            expr = "False"
            assert = 2
            {task_ignore("expr_fail_2")}

            [tool.poe.tasks.script_fail_1]
            script = "sys:exit(1)"
            {task_ignore("script_fail_1")}

            [tool.poe.tasks.script_fail_2]
            script = "sys:exit(2)"
            {task_ignore("script_fail_2")}
        """

        return temp_pyproject(project_tmpl)

    return generator


@pytest.fixture
def generate_ref_pyproject(temp_pyproject):
    def generator(ref_invalid_ignore_fail=False):
        project_tmpl = f"""
            [tool.poe.tasks.target_fail]
            cmd = "poe_test_fail 0 1"

            [tool.poe.tasks.target_ignore]
            cmd = "poe_test_fail 0 1"
            ignore_fail = true

            [tool.poe.tasks.ref_no_ignore]
            ref = "target_fail"

            [tool.poe.tasks.ref_ignore]
            ref = "target_fail"
            ignore_fail = true

            [tool.poe.tasks.ref_child_ignore]
            ref = "target_ignore"

            [tool.poe.tasks.ref_both_ignore]
            ref = "target_ignore"
            ignore_fail = true

            [tool.poe.tasks.seq_fail]
            sequence = ["target_fail", "target_fail"]

            [tool.poe.tasks.ref_seq_no_ignore]
            ref = "seq_fail"

            [tool.poe.tasks.ref_seq_ignore]
            ref = "seq_fail"
            ignore_fail = true

            [tool.poe.tasks.ref_invalid]
            ref = "target_fail"
            {fmt_ignore_fail(ref_invalid_ignore_fail)}
        """

        return temp_pyproject(project_tmpl)

    return generator


@pytest.fixture
def generate_composed_pyproject(temp_pyproject):
    def generator():
        project_tmpl = """
            [tool.poe.tasks]
            ok_task = "poe_test_echo ok"
            child_ignore_true = { cmd = "poe_test_fail 0 1", ignore_fail = true }
            child_ignore_list = { cmd = "poe_test_fail 0 2", ignore_fail = [2] }
            child_fail_a = "poe_test_fail 0 1"
            child_fail_b = "poe_test_fail 0 1"
            dep_fail_ignore = { cmd = "poe_test_fail 0 1", ignore_fail = true }
            dep_fail_list = { cmd = "poe_test_fail 0 2", ignore_fail = [2] }
            dep_fail_plain = "poe_test_fail 0 1"

            [tool.poe.tasks.parent_seq_no_ignore]
            sequence = ["child_ignore_true", "child_ignore_list", "ok_task"]

            [tool.poe.tasks.parent_par_no_ignore]
            parallel = ["child_ignore_true", "child_ignore_list", "ok_task"]

            [tool.poe.tasks.child_seq_return_non_zero]
            sequence = ["child_fail_a", "child_fail_b"]
            ignore_fail = "return_non_zero"

            [tool.poe.tasks.child_par_return_non_zero]
            parallel = ["child_fail_a", "child_fail_b"]
            ignore_fail = "return_non_zero"

            [tool.poe.tasks.parent_seq_ignore_true]
            sequence = ["child_seq_return_non_zero", "ok_task"]
            ignore_fail = true

            [tool.poe.tasks.parent_par_ignore_true]
            parallel = ["child_seq_return_non_zero", "ok_task"]
            ignore_fail = true

            [tool.poe.tasks.ref_seq_return_non_zero]
            ref = "child_seq_return_non_zero"

            [tool.poe.tasks.ref_seq_return_non_zero_ignore]
            ref = "child_seq_return_non_zero"
            ignore_fail = true

            [tool.poe.tasks.ref_par_return_non_zero]
            ref = "child_par_return_non_zero"

            [tool.poe.tasks.ref_par_return_non_zero_ignore]
            ref = "child_par_return_non_zero"
            ignore_fail = true

            [tool.poe.tasks.graph_root]
            cmd = "poe_test_echo graph"
            deps = ["dep_fail_ignore", "dep_fail_list"]

            [tool.poe.tasks.graph_root_fail]
            cmd = "poe_test_echo graph_fail"
            deps = ["dep_fail_plain"]

            [tool.poe.tasks.ref_graph_root_fail_ignore]
            ref = "graph_root_fail"
            ignore_fail = true
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


def test_invalid_ignore_list_value(generate_pyproject, run_poe):
    project_path = generate_pyproject(lvl1_ignore_fail=[1])
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
    result = run_poe("lvl1_seq", cwd=project_path)
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
    assert "Warning: Sequence aborted after failed subtask 'task_1'" in result.capture
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
        in result.capture
    )
    assert "Error: Subtask 'lvl1_seq' returned non-zero exit status" in result.capture


@pytest.mark.parametrize(
    ("_task_type", "task_name", "capture_hint", "expected_code"),
    EXEC_TASK_CASES,
    ids=EXEC_TASK_IDS,
)
def test_exec_without_ignore(
    generate_exec_pyproject, run_poe, _task_type, task_name, capture_hint, expected_code
):
    project_path = generate_exec_pyproject()
    result = run_poe(task_name, cwd=project_path)
    assert result.code == expected_code, "Expected non-zero result"
    assert capture_hint in result.capture


@pytest.mark.parametrize(
    ("_task_type", "task_name", "capture_hint", "_expected_code"),
    EXEC_TASK_CASES,
    ids=EXEC_TASK_IDS,
)
def test_exec_ignore_true(
    generate_exec_pyproject,
    run_poe,
    _task_type,
    task_name,
    capture_hint,
    _expected_code,
):
    project_path = generate_exec_pyproject({task_name: True})
    result = run_poe(task_name, cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert capture_hint in result.capture


@pytest.mark.parametrize(
    ("_task_type", "task_name", "capture_hint", "_expected_code"),
    EXEC_TASK_CASES,
    ids=EXEC_TASK_IDS,
)
def test_exec_ignore_list_match(
    generate_exec_pyproject,
    run_poe,
    _task_type,
    task_name,
    capture_hint,
    _expected_code,
):
    project_path = generate_exec_pyproject({task_name: [1]})
    result = run_poe(task_name, cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert capture_hint in result.capture


@pytest.mark.parametrize(
    ("_task_type", "task_name", "capture_hint", "expected_code"),
    EXEC_TASK_FAIL_2_CASES,
    ids=EXEC_TASK_IDS,
)
def test_exec_ignore_list_nonmatch(
    generate_exec_pyproject, run_poe, _task_type, task_name, capture_hint, expected_code
):
    project_path = generate_exec_pyproject({task_name: [1]})
    result = run_poe(task_name, cwd=project_path)
    assert result.code == expected_code, "Expected non-zero result"
    assert capture_hint in result.capture


@pytest.mark.parametrize(
    ("_task_type", "task_name", "capture_hint", "_expected_code"),
    EXEC_TASK_FAIL_2_CASES,
    ids=EXEC_TASK_IDS,
)
def test_exec_ignore_list_multi_match(
    generate_exec_pyproject,
    run_poe,
    _task_type,
    task_name,
    capture_hint,
    _expected_code,
):
    project_path = generate_exec_pyproject({task_name: [1, 2]})
    result = run_poe(task_name, cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert capture_hint in result.capture


@pytest.mark.parametrize("invalid_value", [["1"], "return_non_zero"])
@pytest.mark.parametrize(
    ("_task_type", "task_name", "_capture_hint", "_expected_code"),
    EXEC_TASK_CASES,
    ids=EXEC_TASK_IDS,
)
def test_exec_invalid_ignore_values(
    generate_exec_pyproject,
    run_poe,
    invalid_value,
    _task_type,
    task_name,
    _capture_hint,
    _expected_code,
):
    project_path = generate_exec_pyproject({task_name: invalid_value})
    result = run_poe(task_name, cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "Option 'ignore_fail" in result.capture
    assert "value of type" in result.capture


def test_ref_without_ignore(generate_ref_pyproject, run_poe):
    project_path = generate_ref_pyproject()
    result = run_poe("ref_no_ignore", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "poe_test_fail 0 1" in result.capture


def test_ref_ignore_true(generate_ref_pyproject, run_poe):
    project_path = generate_ref_pyproject()
    result = run_poe("ref_ignore", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert "poe_test_fail 0 1" in result.capture


def test_ref_child_ignore(generate_ref_pyproject, run_poe):
    project_path = generate_ref_pyproject()
    result = run_poe("ref_child_ignore", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert "poe_test_fail 0 1" in result.capture


def test_ref_both_ignore(generate_ref_pyproject, run_poe):
    project_path = generate_ref_pyproject()
    result = run_poe("ref_both_ignore", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert "poe_test_fail 0 1" in result.capture


def test_ref_sequence_without_ignore(generate_ref_pyproject, run_poe):
    project_path = generate_ref_pyproject()
    result = run_poe("ref_seq_no_ignore", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "Sequence aborted after failed subtask 'target_fail'" in result.capture


def test_ref_sequence_ignore_true(generate_ref_pyproject, run_poe):
    project_path = generate_ref_pyproject()
    result = run_poe("ref_seq_ignore", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert (
        "Warning: Sequence aborted after failed subtask 'target_fail'" in result.capture
    )


@pytest.mark.parametrize("invalid_value", [[1], "return_non_zero"])
def test_ref_invalid_ignore_values(generate_ref_pyproject, run_poe, invalid_value):
    project_path = generate_ref_pyproject(ref_invalid_ignore_fail=invalid_value)
    result = run_poe("ref_invalid", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "Option 'ignore_fail' must have a value of type: bool" in result.capture


def test_parent_uses_child_ignore(generate_composed_pyproject, run_poe):
    project_path = generate_composed_pyproject()
    result = run_poe("parent_seq_no_ignore", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert "Poe => poe_test_fail 0 1" in result.capture
    assert "Poe => poe_test_fail 0 2" in result.capture
    assert "Poe => poe_test_echo ok" in result.capture


def test_parallel_parent_uses_child_ignore(generate_composed_pyproject, run_poe):
    project_path = generate_composed_pyproject()
    result = run_poe("parent_par_no_ignore", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert "Poe => poe_test_fail 0 1" in result.capture
    assert "Poe => poe_test_fail 0 2" in result.capture
    assert "Poe => poe_test_echo ok" in result.capture


def test_parent_ignore_true_with_child_return_non_zero(
    generate_composed_pyproject, run_poe
):
    project_path = generate_composed_pyproject()
    result = run_poe("parent_seq_ignore_true", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert (
        "Warning: Subtasks 'child_fail_a', 'child_fail_b' returned non-zero exit status"
        in result.capture
    )
    assert "Poe => poe_test_echo ok" in result.capture


def test_parallel_parent_ignore_true_with_child_return_non_zero(
    generate_composed_pyproject, run_poe
):
    project_path = generate_composed_pyproject()
    result = run_poe("parent_par_ignore_true", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert (
        "Warning: Parallel subtask 'child_seq_return_non_zero' failed with exception"
        in result.capture
    )
    assert "Poe => poe_test_echo ok" in result.capture


def test_ref_return_non_zero(generate_composed_pyproject, run_poe):
    project_path = generate_composed_pyproject()
    result = run_poe("ref_seq_return_non_zero", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "Subtasks 'child_fail_a', 'child_fail_b' returned non-zero exit status" in (
        result.capture
    )


def test_ref_return_non_zero_ignore(generate_composed_pyproject, run_poe):
    project_path = generate_composed_pyproject()
    result = run_poe("ref_seq_return_non_zero_ignore", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert (
        "Warning: Subtasks 'child_fail_a', 'child_fail_b' returned non-zero exit status"
        in result.capture
    )


def test_ref_parallel_return_non_zero(generate_composed_pyproject, run_poe):
    project_path = generate_composed_pyproject()
    result = run_poe("ref_par_return_non_zero", cwd=project_path)
    assert result.code == 1, "Expected non-zero result"
    assert "Subtasks 'child_fail_a', 'child_fail_b' returned non-zero exit status" in (
        result.capture
    )


def test_ref_parallel_return_non_zero_ignore(generate_composed_pyproject, run_poe):
    project_path = generate_composed_pyproject()
    result = run_poe("ref_par_return_non_zero_ignore", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert (
        "Warning: Subtasks 'child_fail_a', 'child_fail_b' returned non-zero exit status"
        in result.capture
    )


def test_task_graph_dep_ignore(generate_composed_pyproject, run_poe):
    project_path = generate_composed_pyproject()
    result = run_poe("graph_root", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert "Poe => poe_test_fail 0 1" in result.capture
    assert "Poe => poe_test_fail 0 2" in result.capture
    assert "Poe => poe_test_echo graph" in result.capture


def test_ref_task_graph_ignore(generate_composed_pyproject, run_poe):
    project_path = generate_composed_pyproject()
    result = run_poe("ref_graph_root_fail_ignore", cwd=project_path)
    assert result.code == 0, "Expected zero result"
    assert (
        "Warning: Task graph aborted after failed task 'dep_fail_plain'"
        in result.capture
    )
