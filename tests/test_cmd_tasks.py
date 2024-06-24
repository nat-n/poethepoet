from pathlib import Path

import pytest


def test_call_echo_task(run_poe_subproc, projects, esc_prefix, is_windows):
    result = run_poe_subproc("echo", "foo", "!", project="cmds")
    if is_windows:
        assert result.capture == (
            "Poe => poe_test_echo "
            f"'POE_ROOT:{projects['cmds']}' Password1, task_args: foo '!'\n"
        )
    else:
        assert result.capture == (
            "Poe => poe_test_echo "
            f"POE_ROOT:{projects['cmds']} Password1, task_args: foo '!'\n"
        )

    assert result.stdout == f"POE_ROOT:{projects['cmds']} Password1, task_args: foo !\n"
    assert result.stderr == ""


def test_setting_envvar_in_task(run_poe_subproc, projects):
    result = run_poe_subproc("show_env", project="cmds")
    assert result.capture == "Poe => poe_test_env\n"
    assert f"POE_ROOT={projects['cmds']}" in result.stdout
    assert result.stderr == ""


def test_cmd_task_with_dash_case_arg(run_poe_subproc):
    result = run_poe_subproc(
        "greet", "--formal-greeting=hey", "--subject=you", project="cmds"
    )
    assert result.capture == "Poe => poe_test_echo hey you\n"
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
    assert result.capture == "Poe => poe_test_echo hey you guy '!'\n"
    assert result.stdout == "hey you guy !\n"
    assert result.stderr == ""


def test_cmd_alias_env_var(run_poe_subproc):
    result = run_poe_subproc(
        "surfin-bird", project="cmds", env={"SOME_INPUT_VAR": "BIRD"}
    )
    assert result.capture == "Poe => poe_test_echo BIRD is the word\n"
    assert result.stdout == "BIRD is the word\n"
    assert result.stderr == ""


def test_cmd_task_with_multiple_value_arg(run_poe_subproc):
    result = run_poe_subproc("multiple-value-arg", "hey", "1", "2", "3", project="cmds")
    assert result.capture == "Poe => poe_test_echo 'first: hey second: 1 2 3'\n"
    assert result.stdout == "first: hey second: 1 2 3\n"
    assert result.stderr == ""


def test_cmd_task_with_cwd_option(run_poe_subproc, poe_project_path):
    result = run_poe_subproc("cwd", project="cwd")
    assert result.capture == "Poe => poe_test_pwd\n"
    path_parts = ("tests", "fixtures", "cwd_project", "subdir", "foo")
    assert result.stdout == f"{poe_project_path.joinpath(*path_parts)}\n"
    assert result.stderr == ""


def test_cmd_task_with_cwd_option_env(run_poe_subproc, poe_project_path):
    result = run_poe_subproc("cwd_env", project="cwd", env={"BAR_ENV": "bar"})
    assert result.capture == "Poe => poe_test_pwd\n"
    path_parts = ["tests", "fixtures", "cwd_project", "subdir", "bar"]
    assert result.stdout == f"{poe_project_path.joinpath(*path_parts)}\n"
    assert result.stderr == ""


def test_cmd_task_runs_in_project_root_by_default(
    run_poe_subproc, poe_project_path, projects
):
    result = run_poe_subproc(
        "default_pwd",
        project="cwd",
        cwd=poe_project_path.joinpath(
            "tests", "fixtures", "cwd_project", "subdir", "foo"
        ),
    )
    assert result.capture == "Poe => poe_test_pwd\n"
    assert result.stdout == f"{projects['cwd']}\n"
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
    path_parts = ["tests", "fixtures", "cwd_project", "subdir", "foo"]
    assert result.stdout == f"{poe_project_path.joinpath(*path_parts)}\n"
    assert result.stderr == ""


def test_cmd_task_with_cwd_option_pwd_override(run_poe_subproc, poe_project_path):
    result = run_poe_subproc(
        "cwd_poe_pwd",
        project="cwd",
        env={
            "POE_CWD": str(
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
    path_parts = ["tests", "fixtures", "cwd_project", "subdir", "bar"]
    assert result.stdout == f"{poe_project_path.joinpath(*path_parts)}\n"
    assert result.stderr == ""


def test_cmd_task_with_cwd_option_arg(run_poe_subproc, poe_project_path):
    result = run_poe_subproc("cwd_arg", "--foo_var", "foo", project="cwd")
    assert result.capture == "Poe => poe_test_pwd\n"
    path_parts = ["tests", "fixtures", "cwd_project", "subdir", "foo"]
    assert result.stdout == f"{poe_project_path.joinpath(*path_parts)}\n"
    assert result.stderr == ""


def test_cmd_with_complex_token(run_poe_subproc):
    result = run_poe_subproc("ls_color", project="cmds")
    assert result.capture == "Poe => poe_test_echo --color=always 'a b c'\n"
    assert result.stdout == "--color=always a b c\n"
    assert result.stderr == ""


def test_cmd_task_with_with_glob_arg_and_cwd(
    run_poe_subproc, poe_project_path, is_windows
):
    result = run_poe_subproc("ls", "--path-arg", "./subdir", project="cwd")
    assert result.capture == "Poe => ls ./subdir\n"
    assert result.stdout == "bar\nfoo\n"
    assert result.stderr == ""

    result = run_poe_subproc("ls", "--cwd-arg", "subdir", project="cwd")
    assert result.capture == "Poe => ls\n"
    assert result.stdout == "bar\nfoo\n"
    assert result.stderr == ""

    result = run_poe_subproc(
        "ls", "--path-arg", "./f*", "--cwd-arg", "subdir", project="cwd"
    )
    assert result.capture.startswith("Poe => ls ")
    if is_windows:
        assert result.capture.endswith("foo'\n")
    else:
        assert result.capture.endswith("foo\n")
    assert result.stdout == "bar.txt\n"
    assert result.stderr == ""


def test_cmd_with_capture_stdout(run_poe_subproc, projects, poe_project_path):
    result = run_poe_subproc(
        "-C",
        str(projects["cmds"]),
        "meeseeks",
        project="cmds",
        cwd=poe_project_path,
    )
    assert (
        result.capture
        == """Poe <= poe_test_echo 'I'"'"'m Mr. Meeseeks! Look at me!'\n"""
    )
    assert result.stdout == ""
    assert result.stderr == ""

    output_path = Path("message.txt")
    try:
        with output_path.open("r") as output_file:
            assert output_file.read() == "I'm Mr. Meeseeks! Look at me!\n"
    finally:
        output_path.unlink()


@pytest.mark.parametrize(
    "testcase",
    [
        "multiline_no_comments",
        "multiline_with_single_last_line_comment",
        "multiline_with_many_comments",
    ],
)
def test_cmd_multiline(run_poe_subproc, testcase):
    result = run_poe_subproc(testcase, project="cmds")
    assert result.capture == "Poe => poe_test_echo first_arg second_arg\n"
    assert result.stdout == "first_arg second_arg\n"
    assert result.stderr == ""
