def test_call_echo_task(run_poe_subproc, projects, esc_prefix):
    result = run_poe_subproc("echo", "foo", "!", project="cmds")
    assert (
        result.capture
        == f"Poe => echo POE_ROOT:{projects['cmds']} Password1, task_args: foo !\n"
    )
    assert result.stdout == f"POE_ROOT:{projects['cmds']} Password1, task_args: foo !\n"
    assert result.stderr == ""


def test_setting_envvar_in_task(run_poe_subproc, projects):
    result = run_poe_subproc("show_env", project="cmds")
    assert result.capture == f"Poe => env\n"
    assert f"POE_ROOT={projects['cmds']}" in result.stdout
    assert result.stderr == ""


def test_cmd_task_with_dash_case_arg(run_poe_subproc):
    result = run_poe_subproc(
        "greet", "--formal-greeting=hey", "--subject=you", project="cmds"
    )
    assert result.capture == f"Poe => echo $formal_greeting $subject\n"
    assert result.stdout == "hey you\n"
    assert result.stderr == ""
