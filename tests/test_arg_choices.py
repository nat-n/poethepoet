import pytest


@pytest.fixture
def generate_choices_pyproject(temp_pyproject):
    def generator():
        project_tmpl = """
            [tool.poe.tasks.check]
            cmd = "poe_test_echo ${package}"
            [[tool.poe.tasks.check.args]]
            name = "package"
            positional = true
            choices = ["all", "package1", "package2"]
        """

        return temp_pyproject(project_tmpl)

    return generator


@pytest.fixture
def generate_invalid_choices_pyproject(temp_pyproject):
    def generator(arg_block: str):
        project_tmpl = f"""
            [tool.poe.tasks.bad]
            cmd = "poe_test_echo ok"
            args = [{{ {arg_block} }}]
        """

        return temp_pyproject(project_tmpl)

    return generator


@pytest.fixture
def generate_choice_task_pyproject(temp_pyproject):
    def generator(project_tmpl: str):
        return temp_pyproject(project_tmpl)

    return generator


def test_choices_are_listed_in_help(generate_choices_pyproject, run_poe):
    project_path = generate_choices_pyproject()
    result = run_poe("-h", "check", cwd=project_path)
    assert "[choices: 'all', 'package1', 'package2']" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_choices_are_listed_in_task_summary_help(generate_choices_pyproject, run_poe):
    project_path = generate_choices_pyproject()
    result = run_poe(cwd=project_path)
    assert "Configured tasks:" in result.capture
    assert "[choices: 'all', 'package1', 'package2']" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_choices_help_includes_default_and_choices_for_option(
    generate_choice_task_pyproject, run_poe
):
    project_path = generate_choice_task_pyproject("""
            [tool.poe.tasks.check]
            cmd = "poe_test_echo ok"

            [[tool.poe.tasks.check.args]]
            name = "line_length"
            options = ["--line-length", "-l"]
            type = "integer"
            default = 88
            choices = [88, 100]
        """)
    result = run_poe("-h", "check", cwd=project_path)
    assert "--line-length, -l" in result.capture
    assert "[default: 88; choices: 88, 100]" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_choices_accepts_valid_value(generate_choices_pyproject, run_poe):
    project_path = generate_choices_pyproject()
    result = run_poe("check", "all", cwd=project_path)
    assert result.code == 0
    assert result.capture == "Poe => poe_test_echo all\n"
    assert result.stderr == ""


def test_choices_rejects_invalid_value(generate_choices_pyproject, run_poe):
    project_path = generate_choices_pyproject()
    result = run_poe("check", "nope", cwd=project_path)
    assert result.code == 1
    assert "invalid choice: 'nope'" in result.capture
    assert "Error: Invalid arguments for task 'check'" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_choices_allow_whitespace_values(generate_choice_task_pyproject, run_poe):
    project_path = generate_choice_task_pyproject("""
            [tool.poe.tasks.check]
            cmd = "poe_test_echo ${package}"

            [[tool.poe.tasks.check.args]]
            name = "package"
            positional = true
            choices = ["multi word", "single"]
        """)
    result = run_poe("check", "multi word", cwd=project_path)
    assert result.code == 0
    assert result.capture == "Poe => poe_test_echo multi word\n"
    result = run_poe("-h", "check", cwd=project_path)
    assert "[choices: 'multi word', 'single']" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_choices_with_multiple_rejects_invalid_value(
    generate_choice_task_pyproject, run_poe
):
    project_path = generate_choice_task_pyproject("""
            [tool.poe.tasks.check]
            cmd = "poe_test_echo ok"

            [[tool.poe.tasks.check.args]]
            name = "flavor"
            options = ["--flavor"]
            multiple = true
            required = true
            choices = ["vanilla", "choc"]
        """)
    result = run_poe("check", "--flavor", "vanilla", "mint", cwd=project_path)
    assert result.code == 1
    assert "invalid choice: 'mint'" in result.capture
    assert "Error: Invalid arguments for task 'check'" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_choices_templated_default_skips_membership_check(
    generate_choice_task_pyproject, run_poe
):
    project_path = generate_choice_task_pyproject("""
            [tool.poe.tasks.check]
            cmd = "poe_test_echo ${package}"

            [[tool.poe.tasks.check.args]]
            name = "package"
            positional = true
            default = "${CHOICE}"
            choices = ["all"]
        """)
    result = run_poe("-h", "check", cwd=project_path)
    assert "[default: ${CHOICE}; choices: 'all']" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("arg_block", "expected_error"),
    [
        (
            'name = "count", positional = true, type = "integer", choices = ["1", "2"]',
            "invalid choice value '1'",
        ),
        (
            'name = "flag", type = "boolean", choices = [true, false]',
            "invalid choice value True",
        ),
        (
            'name = "mode", choices = "all"',
            "Option 'choices' must have a value of type",
        ),
        (
            'name = "mode", default = "nope", choices = ["ok"]',
            "default value 'nope'",
        ),
        (
            'name = "ratio", type = "float", choices = [1]',
            "invalid choice value 1",
        ),
    ],
    ids=(
        "typed_mismatch",
        "boolean_choices",
        "choices_not_list",
        "default_not_in_choices",
        "float_int_mismatch",
    ),
)
def test_invalid_choices_config(
    generate_invalid_choices_pyproject, run_poe, arg_block, expected_error
):
    project_path = generate_invalid_choices_pyproject(arg_block)
    result = run_poe("bad", cwd=project_path)
    assert result.code == 1
    assert "Invalid argument" in result.capture
    assert expected_error in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_integer_choices_accept_bool_values(generate_choice_task_pyproject, run_poe):
    project_path = generate_choice_task_pyproject("""
            [tool.poe.tasks.check]
            cmd = "poe_test_echo ${count}"

            [[tool.poe.tasks.check.args]]
            name = "count"
            positional = true
            type = "integer"
            choices = [true]
        """)
    result = run_poe("check", "1", cwd=project_path)
    assert result.code == 1
    assert "Invalid argument 'count' declared" in result.capture
    assert "invalid choice value True" in result.capture
    assert "type the configured 'integer'" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""
