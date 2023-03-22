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
    assert result.capture == f"Poe => poe_test_echo hey you\n"
    assert result.stdout == "hey you\n"
    assert result.stderr == ""


def test_cmd_task_with_args_and_extra_args(run_poe_subproc):
    result = run_poe_subproc(
        "greet",
        "--formal-greeting=hey",
        "--subject=you",
        "--",
        "guy",
        "!",
        project="cmds",
    )
    assert result.capture == f"Poe => poe_test_echo hey you guy !\n"
    assert result.stdout == "hey you guy !\n"
    assert result.stderr == ""


def test_cmd_alias_env_var(run_poe_subproc):
    result = run_poe_subproc(
        "surfin-bird", project="cmds", env={"SOME_INPUT_VAR": "BIRD"}
    )
    assert result.capture == f"Poe => poe_test_echo BIRD is the word\n"
    assert result.stdout == "BIRD is the word\n"
    assert result.stderr == ""


def test_cmd_task_with_multiple_value_arg(run_poe_subproc, is_windows):
    result = run_poe_subproc("multiple-value-arg", "hey", "1", "2", "3", project="cmds")
    if is_windows:
        assert result.capture == 'Poe => poe_test_echo "first: hey second: 1 2 3"\n'
        assert result.stdout == '"first: hey second: 1 2 3"\n'
    else:
        assert result.capture == "Poe => poe_test_echo first: hey second: 1 2 3\n"
        assert result.stdout == "first: hey second: 1 2 3\n"
    assert result.stderr == ""


def test_cmd_task_with_cwd_option(run_poe_subproc, poe_project_path):
    result = run_poe_subproc("cwd", project="cwd")
    assert result.capture == "Poe => poe_test_pwd\n"
    assert (
        result.stdout
        == f'{poe_project_path.joinpath("tests", "fixtures", "cwd_project", "subdir", "foo")}\n'
    )
    assert result.stderr == ""
