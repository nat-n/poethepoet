def test_call_echo_task(run_poe_subproc, projects, esc_prefix):
    result = run_poe_subproc("echo", "foo", "!", project="cmds")
    assert (
        result.capture
        == f"Poe => poe_test_echo POE_ROOT:{projects['cmds']} Password1, task_args: foo !\n"
    )
    assert result.stdout == f"POE_ROOT:{projects['cmds']} Password1, task_args: foo !\n"
    assert result.stderr == ""


def test_setting_envvar_in_task(run_poe_subproc, projects):
    result = run_poe_subproc("show_env", project="cmds")
    assert result.capture == f"Poe => poe_test_env\n"
    assert f"POE_ROOT={projects['cmds']}" in result.stdout
    assert result.stderr == ""


def test_cmd_task_with_dash_case_arg(run_poe_subproc):
    result = run_poe_subproc(
        "greet", "--formal-greeting=hey", "--subject=you", project="cmds"
    )
    assert result.capture == f"Poe => poe_test_echo $formal_greeting $subject\n"
    assert result.stdout == "hey you\n"
    assert result.stderr == ""


def test_cmd_alias_env_var(run_poe_subproc):
    result = run_poe_subproc(
        "surfin-bird", project="cmds", env={"SOME_INPUT_VAR": "BIRD"}
    )
    assert result.capture == f"Poe => poe_test_echo BIRD is the word\n"
    assert result.stdout == "BIRD is the word\n"
    assert result.stderr == ""


def test_cmd_multiple_value_arg(run_poe_subproc):
    result = run_poe_subproc("multiple-value-arg", "hey", "1", "2", "3", project="cmds")
    assert result.capture == "Poe => poe_test_echo first: hey second: 1 2 3\n"
    assert result.stdout == "first: hey second: 1 2 3\n"
    assert result.stderr == ""
