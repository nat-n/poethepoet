import os


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


def test_cmd_task_with_multiple_value_arg(run_poe_subproc):
    result = run_poe_subproc("multiple-value-arg", "hey", "1", "2", "3", project="cmds")
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


def test_cmd_task_with_cwd_option_env(run_poe_subproc, poe_project_path):
    result = run_poe_subproc("cwd_env", project="cwd", env={"BAR_ENV": "bar"})
    assert result.capture == "Poe => poe_test_pwd\n"
    assert (
        result.stdout
        == f'{poe_project_path.joinpath("tests", "fixtures", "cwd_project", "subdir", "bar")}\n'
    )
    assert result.stderr == ""


def test_cmd_task_with_cwd_option_pwd(run_poe_subproc, poe_project_path):
    result = run_poe_subproc(
        "cwd_poe_pwd",
        project="cwd",
        cwd=poe_project_path.joinpath(
            "tests", "fixtures", "cwd_project", "subdir", "foo"
        ),
    )
    assert result.capture == "Poe => poe_test_pwd\n"
    assert (
        result.stdout
        == f'{poe_project_path.joinpath("tests", "fixtures", "cwd_project", "subdir", "foo")}\n'
    )
    assert result.stderr == ""


def test_cmd_task_with_cwd_option_pwd_override(run_poe_subproc, poe_project_path):
    result = run_poe_subproc(
        "cwd_poe_pwd",
        project="cwd",
        env={
            "POE_PWD": str(
                poe_project_path.joinpath(
                    "tests", "fixtures", "cwd_project", "subdir", "bar"
                )
            )
        },
        cwd=poe_project_path.joinpath(
            "tests", "fixtures", "cwd_project", "subdir", "foo"
        ),
    )
    assert result.capture == "Poe => poe_test_pwd\n"
    assert (
        result.stdout
        == f'{poe_project_path.joinpath("tests", "fixtures", "cwd_project", "subdir", "bar")}\n'
    )
    assert result.stderr == ""


def test_cmd_task_with_cwd_option_arg(run_poe_subproc, poe_project_path):
    result = run_poe_subproc("cwd_arg", "--foo_var", "foo", project="cwd")
    assert result.capture == "Poe => poe_test_pwd\n"
    assert (
        result.stdout
        == f'{poe_project_path.joinpath("tests", "fixtures", "cwd_project", "subdir", "foo")}\n'
    )
    assert result.stderr == ""


def test_cmd_task_with_with_glob_arg_and_cwd(run_poe_subproc, poe_project_path):
    result = run_poe_subproc("ls", "--path-arg", "./subdir", project="cwd")
    assert result.capture == "Poe => ls ./subdir\n"
    assert result.stdout == f"bar\nfoo\n"
    assert result.stderr == ""

    result = run_poe_subproc("ls", "--cwd-arg", "subdir", project="cwd")
    assert result.capture == "Poe => ls\n"
    assert result.stdout == f"bar\nfoo\n"
    assert result.stderr == ""

    result = run_poe_subproc(
        "ls", "--path-arg", "./f*", "--cwd-arg", "subdir", project="cwd"
    )
    assert result.capture.startswith("Poe => ls ")
    assert result.capture.endswith("foo\n")
    assert result.stdout == f"bar.txt\n"
    assert result.stderr == ""
