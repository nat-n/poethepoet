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


def test_setting_envvar_in_task(run_poe, projects):
    result = run_poe("show_env", project="cmds")
    assert result.capture == "Poe => poe_test_env\n"
    assert f"POE_ROOT={projects['cmds']}" in result.stdout
    assert result.stderr == ""


def test_cmd_task_with_dash_case_arg(run_poe):
    result = run_poe("greet", "--formal-greeting=hey", "--subject=you", project="cmds")
    assert result.capture == "Poe => poe_test_echo hey you\n"
    assert result.stdout == "hey you\n"
    assert result.stderr == ""


def test_cmd_task_with_args_and_extra_args(run_poe):
    result = run_poe(
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


def test_cmd_alias_env_var(run_poe):
    result = run_poe("surfin-bird", project="cmds", env={"SOME_INPUT_VAR": "BIRD"})
    assert result.capture == "Poe => poe_test_echo BIRD is the word\n"
    assert result.stdout == "BIRD is the word\n"
    assert result.stderr == ""


def test_cmd_task_with_multiple_value_arg(run_poe):
    result = run_poe("multiple-value-arg", "hey", "1", "2", "3", project="cmds")
    assert result.capture == "Poe => poe_test_echo 'first: hey second: 1 2 3'\n"
    assert result.stdout == "first: hey second: 1 2 3\n"
    assert result.stderr == ""


def test_cmd_task_with_cwd_option(run_poe, poe_project_path):
    result = run_poe("cwd", project="cwd")
    assert result.capture == "Poe => poe_test_pwd\n"
    path_parts = ("tests", "fixtures", "cwd_project", "subdir", "foo")
    assert result.stdout == f"{poe_project_path.joinpath(*path_parts)}\n"
    assert result.stderr == ""


def test_cmd_task_with_cwd_option_env(run_poe, poe_project_path):
    result = run_poe("cwd_env", project="cwd", env={"BAR_ENV": "bar"})
    assert result.capture == "Poe => poe_test_pwd\n"
    path_parts = ["tests", "fixtures", "cwd_project", "subdir", "bar"]
    assert result.stdout == f"{poe_project_path.joinpath(*path_parts)}\n"
    assert result.stderr == ""


def test_cmd_task_runs_in_project_root_by_default(run_poe, poe_project_path, projects):
    result = run_poe(
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


def test_cmd_task_with_cwd_option_arg(run_poe, poe_project_path):
    result = run_poe("cwd_arg", "--foo_var", "foo", project="cwd")
    assert result.capture == "Poe => poe_test_pwd\n"
    path_parts = ["tests", "fixtures", "cwd_project", "subdir", "foo"]
    assert result.stdout == f"{poe_project_path.joinpath(*path_parts)}\n"
    assert result.stderr == ""


def test_cmd_with_complex_token(run_poe):
    result = run_poe("ls_color", project="cmds")
    assert result.capture == "Poe => poe_test_echo --color=always 'a b c'\n"
    assert result.stdout == "--color=always a b c\n"
    assert result.stderr == ""


def test_cmd_task_with_with_glob_arg_and_cwd(run_poe, poe_project_path, is_windows):
    result = run_poe("ls", "--path-arg", "./subdir", project="cwd")
    assert result.capture == "Poe => ls ./subdir\n"
    assert result.stdout == "bar\nfoo\n"
    assert result.stderr == ""

    result = run_poe("ls", "--cwd-arg", "subdir", project="cwd")
    assert result.capture == "Poe => ls\n"
    assert result.stdout == "bar\nfoo\n"
    assert result.stderr == ""

    result = run_poe("ls", "--path-arg", "./f*", "--cwd-arg", "subdir", project="cwd")
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
def test_cmd_multiline(run_poe, testcase):
    result = run_poe(testcase, project="cmds")
    assert result.capture == "Poe => poe_test_echo first_arg second_arg\n"
    assert result.stdout == "first_arg second_arg\n"
    assert result.stderr == ""


def test_cmd_with_empty_glob_pass(run_poe, is_windows):
    result = run_poe("try-globs-pass", project="cmds")
    assert result.capture.startswith("Poe => poe_test_echo ")
    if is_windows:
        assert result.capture.endswith("tests\\fixtures\\cmds_project' - 'n*thing'\n")
        assert result.stdout.endswith("tests\\fixtures\\cmds_project - n*thing\n")
    else:
        assert result.capture.endswith("tests/fixtures/cmds_project - 'n*thing'\n")
        assert result.stdout.endswith("tests/fixtures/cmds_project - n*thing\n")
    assert result.stderr == ""


def test_cmd_with_empty_glob_null(run_poe, is_windows):
    result = run_poe("try-globs-null", project="cmds")
    assert result.capture.startswith("Poe => poe_test_echo ")
    if is_windows:
        assert result.capture.endswith("tests\\fixtures\\cmds_project' -\n")
        assert result.stdout.endswith("tests\\fixtures\\cmds_project -\n")
    else:
        assert result.capture.endswith("tests/fixtures/cmds_project -\n")
        assert result.stdout.endswith("tests/fixtures/cmds_project -\n")
    assert result.stderr == ""


def test_cmd_with_empty_glob_fail(run_poe):
    result = run_poe("try-globs-fail", project="cmds")
    assert result.capture.startswith(
        "Error: Glob pattern 'n*thing' did not match any files in working directory"
    )
    assert result.stderr == ""


def test_cmd_boolean_flag(run_poe):
    result = run_poe(
        "booleans",
        "--non",
        "--tru",
        "--fal",
        "--txt",
        project="cmds",
    )
    assert result.capture == (
        r"""Poe => poe_test_echo '
${non}=True' '${non:+plus}=plus' '${non:-minus}=True
${fal}=True' '${fal:+plus}=plus' '${fal:-minus}=True
${tru}=' '${tru:+plus}=' '${tru:-minus}=minus
${txt}=' '${txt:+plus}=' '${txt:-minus}=minus'
"""
    )
    assert result.stdout.endswith(
        """
${non}=True ${non:+plus}=plus ${non:-minus}=True
${fal}=True ${fal:+plus}=plus ${fal:-minus}=True
${tru}= ${tru:+plus}= ${tru:-minus}=minus
${txt}= ${txt:+plus}= ${txt:-minus}=minus
""".lstrip()
    )


def test_cmd_boolean_flag_default_value(run_poe):
    result = run_poe("booleans", project="cmds")
    assert result.capture == (
        r"""Poe => poe_test_echo '
${non}=' '${non:+plus}=' '${non:-minus}=minus
${fal}=' '${fal:+plus}=' '${fal:-minus}=minus
${tru}=True' '${tru:+plus}=plus' '${tru:-minus}=True
${txt}=text' '${txt:+plus}=plus' '${txt:-minus}=text'
"""
    )
    assert result.stdout.endswith(
        """
${non}= ${non:+plus}= ${non:-minus}=minus
${fal}= ${fal:+plus}= ${fal:-minus}=minus
${tru}=True ${tru:+plus}=plus ${tru:-minus}=True
${txt}=text ${txt:+plus}=plus ${txt:-minus}=text
""".lstrip()
    )


def test_cmd_boolean_flag_partial_negate_true(run_poe):
    """Only --tru passed: negates default=true to False (unset), others keep defaults"""
    result = run_poe(
        "booleans",
        "--tru",
        project="cmds",
    )
    assert result.stdout.endswith(
        """
${non}= ${non:+plus}= ${non:-minus}=minus
${fal}= ${fal:+plus}= ${fal:-minus}=minus
${tru}= ${tru:+plus}= ${tru:-minus}=minus
${txt}=text ${txt:+plus}=plus ${txt:-minus}=text
""".lstrip()
    )


def test_cmd_boolean_flag_partial_negate_string(run_poe):
    """--txt negates default="text" to False (unset), others keep defaults"""
    result = run_poe(
        "booleans",
        "--txt",
        project="cmds",
    )
    assert result.stdout.endswith(
        """
${non}= ${non:+plus}= ${non:-minus}=minus
${fal}= ${fal:+plus}= ${fal:-minus}=minus
${tru}=True ${tru:+plus}=plus ${tru:-minus}=True
${txt}= ${txt:+plus}= ${txt:-minus}=minus
""".lstrip()
    )


def test_cmd_int_zero_default(run_poe):
    result = run_poe("int_zero_default", project="cmds")
    assert result.capture == "Poe => poe_test_echo 0\n"
    assert result.stdout.strip() == "0"


def test_cmd_int_zero_explicit(run_poe):
    result = run_poe("int_zero_default", "--count", "0", project="cmds")
    assert result.capture == "Poe => poe_test_echo 0\n"
    assert result.stdout.strip() == "0"


def test_cmd_bool_env_collision_flag_set(run_poe):
    result = run_poe("bool_env_collision", "--MY_FLAG", project="cmds")
    assert result.capture == "Poe => poe_test_echo True\n"
    assert result.stdout.strip() == "True"


def test_cmd_bool_env_collision_flag_unset(run_poe):
    result = run_poe("bool_env_collision", project="cmds")
    assert result.capture == "Poe => poe_test_echo fallback\n"
    assert result.stdout.strip() == "fallback"


def test_cmd_bool_env_presence_true(run_poe):
    result = run_poe("bool_env_presence", project="cmds")
    assert result.stdout.strip() == "True 'True'"


def test_cmd_bool_env_presence_false_is_unset(run_poe):
    result = run_poe("bool_env_presence", "--MY_FLAG", project="cmds")
    assert result.stdout.strip() == "False None"


def test_private_env_var_filtered_from_subprocess(run_poe, is_windows):
    """Env vars starting with _ (no uppercase) are filtered from subprocess"""
    result = run_poe("private_env_vars", project="cmds")
    stdout_lower = result.stdout.lower()
    assert "normal=visible" in stdout_lower
    if is_windows:
        # Windows env vars are case-insensitive so _secret and _SECRET
        # collide; only one survives and it won't be filtered as private
        assert "_secret=" in stdout_lower
    else:
        assert "_secret=hidden" not in result.stdout
        assert "_SECRET=VISIBLE" in result.stdout


def test_private_env_var_accessible_in_template(run_poe):
    """Private vars are still available for template resolution"""
    result = run_poe("private_env_template", project="cmds")
    assert result.stdout.strip() == "hidden:VISIBLE:visible"


def test_private_arg_filtered_from_subprocess(
    run_poe,
    is_windows,
):
    """Boolean arg named _flag (no uppercase) is private, _FLAG is not"""
    result = run_poe("private_arg", project="cmds")
    stdout_lower = result.stdout.lower()
    if is_windows:
        assert "_flag=" in stdout_lower
    else:
        assert "_flag=True" not in result.stdout
        assert "_FLAG=True" in result.stdout


def test_private_arg_negated_not_in_subprocess(run_poe):
    """Inferred option names strip leading underscores from arg names"""
    result = run_poe("private_arg", "--flag", "--FLAG", project="cmds")
    assert result.capture == "Poe => poe_test_env\n"
    stdout_lower = result.stdout.lower()
    assert "_flag=" not in stdout_lower
    assert result.stderr == ""


def test_private_arg_accessible_in_template(run_poe):
    """Private args resolve in cmd templates despite subprocess filtering"""
    result = run_poe("private_arg_in_template", project="cmds")
    assert result.stdout.strip() == "True:True"


def test_private_shorthand_arg_uses_stripped_inferred_option_names(run_poe):
    """Short-form arg names infer CLI options without leading underscores"""
    result = run_poe(
        "private_shorthand_arg",
        "--secret",
        "hidden",
        "--PUBLIC",
        "VISIBLE",
        project="cmds",
    )
    assert result.capture == "Poe => poe_test_echo hidden:VISIBLE\n"
    assert result.stdout == "hidden:VISIBLE\n"
    assert result.stderr == ""


def test_private_shorthand_arg_old_option_name_is_rejected(run_poe):
    """The old inferred option form with the leading underscore is no longer accepted"""
    result = run_poe("private_shorthand_arg", "--_secret", "hidden", project="cmds")
    assert "unrecognized arguments: --_secret hidden" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_private_arg_explicit_option_keeps_leading_underscore(run_poe):
    """Explicitly configured options are unaffected by shorthand inference changes"""
    result = run_poe("private_explicit_option", "--_secret", "hidden", project="cmds")
    assert result.capture == "Poe => poe_test_echo hidden\n"
    assert result.stdout == "hidden\n"
    assert result.stderr == ""


def test_multi_value_not_provided_is_unset(run_poe):
    """Multiple arg not provided at all: env var is unset (argparse returns None)"""
    result = run_poe("multi_value_env", project="cmds")
    assert result.stdout.strip() == "False None"


def test_multi_value_provided_with_values(run_poe):
    """Multiple arg with values: env var is space-separated string"""
    result = run_poe("multi_value_env", "--items", "1", "2", "3", project="cmds")
    assert result.stdout.strip() == "True '1 2 3'"


def test_multi_value_provided_empty(run_poe):
    """Multiple arg provided with no values (--items with nothing): env var is unset"""
    result = run_poe("multi_value_env", "--items", project="cmds")
    assert result.stdout.strip() == "False None"


def test_cmd_task_with_poe_extra_args(run_poe):
    """A cmd task referencing $POE_EXTRA_ARGS expands them rather than appending"""
    result = run_poe("echo-extra-args", "foo", "bar", project="cmds")
    assert result.capture == "Poe => poe_test_echo extra: foo bar\n"
    assert result.stdout == "extra: foo bar\n"
    assert result.stderr == ""


def test_cmd_task_with_poe_extra_args_and_named_arg(run_poe):
    """A cmd task with both named args and $POE_EXTRA_ARGS references works correctly"""
    result = run_poe(
        "echo-extra-args-with-named",
        "--prefix=hello",
        "--",
        "foo",
        "bar",
        project="cmds",
    )
    assert result.capture == "Poe => poe_test_echo hello extra: foo bar\n"
    assert result.stdout == "hello extra: foo bar\n"
    assert result.stderr == ""


def test_cmd_task_with_poe_extra_args_and_trailing_args(run_poe):
    """$POE_EXTRA_ARGS in a cmd task can have args both before and after"""
    result = run_poe("echo-extra-args-trailing", "foo", "bar", project="cmds")
    assert result.capture == "Poe => poe_test_echo before: foo bar :after\n"
    assert result.stdout == "before: foo bar :after\n"
    assert result.stderr == ""
