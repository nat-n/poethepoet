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
