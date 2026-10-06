import pytest


def test_global_envfile_and_default(run_poe):
    result = run_poe("test", project="default_value")
    assert (
        "Poe => poe_test_echo '!one!' '!two!' '!three!' '!four!' '!five!' '!six!'\n"
        in result.capture
    )
    assert result.stdout == "!one! !two! !three! !four! !five! !six!\n"
    assert result.stderr == ""


def test_global_envfile_and_default_with_presets(run_poe):
    env = {
        "ONE": "111",
        "TWO": "222",
        "THREE": "333",
        "FOUR": "444",
        "FIVE": "555",
        "SIX": "666",
    }

    result = run_poe("test", project="default_value", env=env)
    assert (
        "Poe => poe_test_echo '!one!' '!two!' '!three!' 444 '!five!' 666\n"
        in result.capture
    )
    assert result.stdout == "!one! !two! !three! 444 !five! 666\n"
    assert result.stderr == ""


def test_invalid_templated_boolean_default_names_task_and_arg(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.check]
        cmd = "poe_test_echo loud=${loud}"
        args = [{ name = "loud", type = "boolean", default = "${POE_TEST_LOUD}" }]
        """)
    result = run_poe("check", cwd=project_path, env={"POE_TEST_LOUD": "yes"})
    assert result.code == 1
    assert (
        "Error: Invalid default for argument 'loud' in task 'check'\n"
        "     | Cannot interpret 'yes' as a boolean"
    ) in result.capture
    assert result.stdout == ""


@pytest.mark.parametrize(
    ("arg_options", "expected"),
    [
        ('type = "integer", default = "5"', "5"),
        ('type = "integer", default = "5", multiple = true', "[5]"),
        ('type = "integer", default = "${POE_TEST_NUM}"', "7"),
        ('type = "integer", default = "${POE_TEST_NUM}", multiple = true', "[7]"),
        ('type = "integer", default = 2.0', "2"),
        ('type = "float", default = 1', "1.0"),
        ('type = "float", default = "1.5", multiple = 2', "[1.5]"),
        ('type = "string", default = 5', "'5'"),
        ('type = "string", default = 5, multiple = true', "['5']"),
        ('default = "${POE_TEST_NUM}"', "'7'"),
    ],
)
def test_arg_default_is_converted_to_arg_type(
    temp_pyproject, run_poe, arg_options, expected
):
    project_path = temp_pyproject(f"""
        [tool.poe.tasks.show]
        expr = "repr(value)"
        args = [{{ name = "value", {arg_options} }}]
        """)
    result = run_poe("show", cwd=project_path, env={"POE_TEST_NUM": "7"})
    assert result.code == 0, result.capture
    assert result.stdout == f"{expected}\n"
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("arg_options", "expected_error"),
    [
        ('type = "integer", default = "abc"', "Cannot interpret 'abc' as an integer"),
        (
            'type = "integer", default = "x", multiple = true',
            "Cannot interpret 'x' as an integer",
        ),
        ('type = "integer", default = 1.5', "Cannot interpret 1.5 as an integer"),
        ('type = "integer", default = true', "Cannot interpret True as an integer"),
        ('type = "float", default = "abc"', "Cannot interpret 'abc' as a float"),
        ('type = "float", default = true', "Cannot interpret True as a float"),
    ],
)
def test_invalid_arg_default_is_rejected_as_config_error(
    temp_pyproject, run_poe, arg_options, expected_error
):
    project_path = temp_pyproject(f"""
        [tool.poe.tasks.show]
        expr = "repr(value)"
        args = [{{ name = "value", {arg_options} }}]
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 1
    assert (
        "Error: Invalid argument 'value' declared in task 'show'\n"
        f"     | {expected_error}"
    ) in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize("multiple", ["false", "true"])
def test_invalid_templated_arg_default_names_task_and_arg(
    temp_pyproject, run_poe, multiple
):
    project_path = temp_pyproject(f"""
        [tool.poe.tasks.show]
        expr = "repr(value)"
        [[tool.poe.tasks.show.args]]
        name = "value"
        type = "integer"
        default = "${{POE_TEST_NUM}}"
        multiple = {multiple}
        """)
    env = {"POE_TEST_NUM": "abc"}
    result = run_poe("show", cwd=project_path, env=env)
    assert result.code == 1
    assert (
        "Error: Invalid default for argument 'value' in task 'show'\n"
        "     | Cannot interpret 'abc' as an integer"
    ) in result.capture
    assert "Invalid arguments for task" not in result.capture
    assert result.stdout == ""

    # The default isn't needed when a value is given on the command line
    result = run_poe("show", "--value", "3", cwd=project_path, env=env)
    assert result.code == 0, result.capture
    assert result.stdout == ("[3]\n" if multiple == "true" else "3\n")
