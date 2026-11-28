import pytest


def test_matrix_runs_all_combinations(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        task.cmd = "poe_test_echo py=${py}"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.capture == (
        "Poe => poe_test_echo py=3.11\nPoe => poe_test_echo py=3.12\n"
    )
    assert result.stdout == "py=3.11\npy=3.12\n"
    assert result.stderr == ""


def test_matrix_expands_cartesian_product_in_declaration_order(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.build]
        matrix = { "py" = ["3.11", "3.12"], "arch" = ["x86", "x64"] }
        task.cmd = "poe_test_echo ${py}-${arch}"
        """)
    result = run_poe("build", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.capture == (
        "Poe => poe_test_echo 3.11-x86\n"
        "Poe => poe_test_echo 3.11-x64\n"
        "Poe => poe_test_echo 3.12-x86\n"
        "Poe => poe_test_echo 3.12-x64\n"
    )
    assert result.stdout == "3.11-x86\n3.11-x64\n3.12-x86\n3.12-x64\n"


def test_matrix_combination_can_be_run_by_name(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        task.cmd = "poe_test_echo py=${py}"
        """)
    for version in ("3.11", "3.12"):
        result = run_poe(f"test-py{version}", cwd=project_path)
        assert result.code == 0, result.capture
        assert result.capture == f"Poe => poe_test_echo py={version}\n"
        assert result.stdout == f"py={version}\n"
        assert result.stderr == ""


def test_matrix_generated_names_include_every_dimension(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.build]
        matrix = { "py" = ["3.11"], "arch" = ["x86"] }
        task.cmd = "poe_test_echo ${py}-${arch}"
        """)
    result = run_poe("build-py3.11-archx86", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "3.11-x86\n"


def test_matrix_combinations_are_not_listed_in_help(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        help = "Run tests for all python versions"
        matrix = { "py" = ["3.11", "3.12"] }
        task.cmd = "poe_test_echo py=${py}"
        """)
    result = run_poe(cwd=project_path)
    assert result.code == 1, result.capture
    assert "test-py3.11" not in result.capture
    assert "test-py3.12" not in result.capture
    assert "test" in result.capture


def test_matrix_task_option_accepts_a_string(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        task = "poe_test_echo py=${py}"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "py=3.11\npy=3.12\n"


def test_matrix_variables_are_visible_to_the_subtask_env_option(
    temp_pyproject, run_poe
):
    project_path = temp_pyproject("""
        [tool.poe.tasks.build]
        matrix = { "py" = ["3.11", "3.12"] }
        task.cmd = "poe_test_echo ${TAG}"
        task.env = { TAG = "py${py}" }
        """)
    result = run_poe("build", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "py3.11\npy3.12\n"


@pytest.mark.parametrize(
    ("cli_args", "expected_versions"),
    [
        ((), ("3.11", "3.12")),
        (("--python-versions", "3.12"), ("3.12",)),
        (("--python-versions", "3.11", "3.12"), ("3.11", "3.12")),
    ],
)
def test_matrix_narrows_to_declared_arg_values(
    temp_pyproject, run_poe, cli_args, expected_versions
):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        args = [{ name = "py", options = ["--python-versions"], multiple = true }]
        task.cmd = "poe_test_echo py=${py}"
        """)
    result = run_poe("test", *cli_args, cwd=project_path)
    assert result.code == 0, result.capture
    expected = "".join(f"py={version}\n" for version in expected_versions)
    assert result.stdout == expected


def test_matrix_narrowing_rejects_undeclared_value(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        args = [{ name = "py", options = ["--python-versions"], multiple = true }]
        task.cmd = "poe_test_echo py=${py}"
        """)
    result = run_poe("test", "--python-versions", "3.13", cwd=project_path)
    assert result.code == 1, result.capture
    assert (
        "Error: Value '3.13' for matrix variable 'py' is not one of the declared "
        "values: '3.11', '3.12'" in result.capture
    )
    assert result.stdout == ""


def test_matrix_arg_with_default_is_rejected(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        args = [{ name = "py", options = ["--python-versions"], default = "3.12" }]
        task.cmd = "poe_test_echo py=${py}"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 1, result.capture
    assert "Error: Invalid task 'test'" in result.capture
    assert (
        "Argument 'py' shares its name with a matrix variable and cannot declare a "
        "default value" in result.capture
    )


def test_matrix_dry_run(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        task.cmd = "poe_test_echo py=${py}"
        """)
    result = run_poe("-d", "test", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.capture == (
        "Poe => poe_test_echo py=3.11\nPoe => poe_test_echo py=3.12\n"
    )
    assert result.stdout == ""


def test_matrix_aborts_after_failed_combination(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        task.cmd = "poe_test_fail 0 3"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 3, result.capture
    assert result.capture == (
        "Poe => poe_test_fail 0 3\n"
        "Error: Matrix aborted after failed combination 'test-py3.11'\n"
    )


def test_matrix_task_within_a_sequence(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        task.cmd = "poe_test_echo py=${py}"

        [tool.poe.tasks.all]
        sequence = ["test"]
        """)
    result = run_poe("all", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "py=3.11\npy=3.12\n"


def test_matrix_combination_as_a_dependency(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        task.cmd = "poe_test_echo py=${py}"

        [tool.poe.tasks.check]
        cmd = "poe_test_echo done"
        deps = ["test-py3.11"]
        """)
    result = run_poe("check", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "py=3.11\ndone\n"


def test_matrix_with_non_string_values(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.build]
        matrix = { "count" = [1, 2], "flag" = [true, false] }
        task.cmd = "poe_test_echo ${count}-${flag}"
        """)
    result = run_poe("build", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "1-True\n1-False\n2-True\n2-False\n"
    result = run_poe("build-count2-flagFalse", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "2-False\n"


def test_hidden_matrix_generates_hidden_combinations(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks._test]
        matrix = { "py" = ["3.11"] }
        task.cmd = "poe_test_echo py=${py}"

        [tool.poe.tasks.test]
        sequence = ["_test"]
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "py=3.11\n"

    result = run_poe("_test-py3.11", cwd=project_path)
    assert result.code == 1, result.capture
    assert "cannot be executed directly" in result.capture


def test_matrix_rejects_capture_stdout(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11"] }
        capture_stdout = "out.txt"
        task.cmd = "poe_test_echo py=${py}"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 1, result.capture
    assert "Error: Invalid task 'test'" in result.capture
    assert (
        "Option 'capture_stdout' is not supported by this task type" in result.capture
    )


@pytest.mark.parametrize("banned_option", ["args", "deps", "uses", "uses_env"])
def test_matrix_subtask_may_not_declare_orchestration_options(
    temp_pyproject, run_poe, banned_option
):
    declarations = {
        "args": 'args = ["extra"]',
        "deps": 'deps = ["test-py3.11"]',
        "uses": 'uses = { X = "test-py3.11" }',
        "uses_env": 'uses_env = "test-py3.11"',
    }
    project_path = temp_pyproject(f"""
        [tool.poe.tasks.test]
        matrix = {{ "py" = ["3.11"] }}
        task.cmd = "poe_test_echo py=${{py}}"
        task.{declarations[banned_option]}
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 1, result.capture
    assert "Error: Invalid task 'test'" in result.capture
    assert (
        f"Unsupported option '{banned_option}' for task declared as the 'task' "
        "option of a matrix task" in result.capture
    )


def test_matrix_requires_the_task_option(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11"] }
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 1, result.capture
    assert "Error: Invalid task 'test'" in result.capture
    assert "Missing required option 'task'" in result.capture


def test_matrix_requires_a_non_empty_mapping(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = {}
        task.cmd = "poe_test_echo hello"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 1, result.capture
    assert "Error: Invalid task 'test'" in result.capture
    assert "must declare at least one matrix variable" in result.capture


def test_matrix_content_must_be_a_mapping(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = "py"
        task.cmd = "poe_test_echo hello"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 1, result.capture
    assert "Error: Invalid task 'test'" in result.capture
    assert "Content for MatrixTask must be a dict" in result.capture


@pytest.mark.parametrize("values", ['"3.11"', "[]"])
def test_matrix_variable_values_must_be_a_non_empty_list(
    temp_pyproject, run_poe, values
):
    project_path = temp_pyproject(f"""
        [tool.poe.tasks.test]
        matrix = {{ "py" = {values} }}
        task.cmd = "poe_test_echo py=${{py}}"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 1, result.capture
    assert "Error: Invalid task 'test'" in result.capture
    assert (
        "Matrix variable 'py' must be declared with a non-empty list of values"
        in result.capture
    )


def test_matrix_variable_names_must_be_valid_env_var_names(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py-version" = ["3.11"] }
        task.cmd = "poe_test_echo py=${py}"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 1, result.capture
    assert "Error: Invalid task 'test'" in result.capture
    assert (
        "Invalid matrix variable name 'py-version': matrix variable names must be "
        "valid environment variable names" in result.capture
    )


def test_matrix_values_must_be_usable_in_task_names(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3 12"] }
        task.cmd = "poe_test_echo py=${py}"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 1, result.capture
    assert "Error: Invalid task 'test'" in result.capture
    assert "Invalid value '3 12' for matrix variable 'py'" in result.capture


def test_matrix_values_must_be_unique(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.11"] }
        task.cmd = "poe_test_echo py=${py}"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 1, result.capture
    assert "Error: Invalid task 'test'" in result.capture
    assert "Matrix variable 'py' declares duplicate values" in result.capture


def test_matrix_task_type_must_be_determinable(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11"] }
        task.cmd = "poe_test_echo py=${py}"
        task.shell = "echo py=${py}"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 1, result.capture
    assert "Error: Invalid task 'test'" in result.capture
    assert (
        "Cannot determine the task type for the 'task' option of matrix task"
        in result.capture
    )


def test_matrix_generated_name_conflicts_with_another_task(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks."test-py3.11"]
        cmd = "poe_test_echo explicit"

        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        task.cmd = "poe_test_echo py=${py}"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 1, result.capture
    assert "conflicts with" in result.capture
    assert "test-py3.11" in result.capture


def test_matrix_definition_inline_in_a_sequence(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.all]
        sequence = [
            { matrix = { "py" = ["3.11", "3.12"] }, task = "poe_test_echo py=${py}" },
        ]
        """)
    result = run_poe("all", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "py=3.11\npy=3.12\n"


def test_matrix_task_option_can_be_an_inline_ref(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.check]
        cmd = "poe_test_echo checking ${py}"

        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        task.ref = "check"
        """)
    result = run_poe("test", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "checking 3.11\nchecking 3.12\n"


def test_matrix_task_cannot_be_referenced_by_uses(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11"] }
        task.cmd = "poe_test_echo py=${py}"

        [tool.poe.tasks.consumer]
        cmd = "poe_test_echo ${OUT}"
        uses = { OUT = "test" }
        """)
    result = run_poe("consumer", cwd=project_path)
    assert result.code == 1, result.capture
    assert "Error: Invalid task 'consumer'" in result.capture
    assert (
        "'uses' option references task that does not support output capture: 'test'"
        in result.capture
    )


def test_matrix_narrows_to_a_single_valued_arg(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        args = [{ name = "py", options = ["--python-version"] }]
        task.cmd = "poe_test_echo py=${py}"
        """)
    result = run_poe("test", "--python-version", "3.12", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "py=3.12\n"


def test_matrix_forwards_free_args_via_poe_extra_args(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.test]
        matrix = { "py" = ["3.11", "3.12"] }
        task.cmd = "poe_test_echo py=${py} $POE_EXTRA_ARGS"
        """)
    result = run_poe("test", "--flag", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "py=3.11 --flag\npy=3.12 --flag\n"
