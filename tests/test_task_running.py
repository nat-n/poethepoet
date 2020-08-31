import pytest


def test_call_echo_task(run_poe_subproc, dummy_project_path, esc_prefix):
    # The $ has to be escaped or it'll be evaluated by the outer shell and poe will
    # never see it
    result = run_poe_subproc("echo", "foo", esc_prefix + r"${POE_ROOT} !")
    assert (
        result.capture
        == f"Poe => echo POE_ROOT:{dummy_project_path} Password1, task_args: foo {dummy_project_path} !\n"
    )
    assert (
        result.stdout
        == f"POE_ROOT:{dummy_project_path} Password1, task_args: foo {dummy_project_path} !\n"
    )
    assert result.stderr == ""


def test_setting_envvar_in_task(run_poe_subproc, dummy_project_path):
    # The $ has to be escaped or it'll be evaluated by the outer shell and poe will
    # never see it
    result = run_poe_subproc("show_env")
    assert result.capture == f"Poe => env\n"
    assert f"POE_ROOT={dummy_project_path}" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize(
    "input_var, output_var",
    (
        (r"\${POE_ROOT}", "dummy_project_path"),
        (r"\\\$POE_ROOT", r"$" + "POE_ROOT"),
        (r"\${POE_ROOT}", "dummy_project_path"),
        (r"ABC\\\${POE_ROOT}D", r"ABC${" + "POE_ROOT" + "}D"),
        (
            r"1 \${POE_ROOT} 2 \${POE_ROOT} 3 \\\${POE_ROOT} ",
            r"1 dummy_project_path 2 dummy_project_path 3 ${POE_ROOT} ",
        ),
        # It's difficult to add more cases without getting lost in the process of
        # templating and running the subprocess script
    ),
)
def test_passing_envvar_str_to_task(
    input_var, output_var, run_poe_subproc, dummy_project_path, is_windows
):
    if is_windows:
        # the escapes doesn't work the same on windows so remove the extras
        input_var = input_var.replace(r"\$", "$").replace(r"\\", "\\")
    # A further (outer shell escaped) escape can be added to indicate to POE that the $
    # is escaped
    # For the sake of sanity poe leaves the remaining backslashes alone
    result = run_poe_subproc("echo", input_var, "!")
    output_var_ = output_var.replace("dummy_project_path", str(dummy_project_path))
    assert (
        result.capture
        == f"Poe => echo POE_ROOT:{dummy_project_path} Password1, task_args: {output_var_} !\n"
    )
    # assert result.stdout == f"POE_ROOT:{dummy_project_path} task_args: {output_var} !\n"
    assert result.stderr == ""


def test_shell_task(run_poe_subproc):
    result = run_poe_subproc("count")
    assert (
        result.capture
        == f"Poe => echo 1 && echo 2 && echo $(python -c 'print(1 + 2)')\n"
    )
    assert result.stdout == "1\n2\n3\n"
    assert result.stderr == ""


def test_shell_task_raises_given_extra_args(run_poe):
    result = run_poe("count", "bla")
    assert f"\n\nError: Shell task 'count' does not accept arguments" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_script_task(run_poe_subproc, dummy_project_path, esc_prefix):
    # The $ has to be escaped or it'll be evaluated by the outer shell and poe will
    # never see it
    result = run_poe_subproc(
        "greet", "nat,", r"welcome to " + esc_prefix + "${POE_ROOT}"
    )
    assert result.capture == f"Poe => greet nat, welcome to {dummy_project_path}\n"
    assert result.stdout == f"hello nat, welcome to {dummy_project_path}\n"
    assert result.stderr == ""


def test_script_task_with_hard_coded_args(
    run_poe_subproc, dummy_project_path, esc_prefix
):
    # The $ has to be escaped or it'll be evaluated by the outer shell and poe will
    # never see it
    result = run_poe_subproc(
        "greet-shouty", "nat,", r"welcome to " + esc_prefix + "${POE_ROOT}"
    )
    assert (
        result.capture == f"Poe => greet-shouty nat, welcome to {dummy_project_path}\n"
    )
    assert result.stdout == f"hello nat, welcome to {dummy_project_path}\n".upper()
    assert result.stderr == ""


def test_ref_task(run_poe_subproc, dummy_project_path, esc_prefix):
    # This should be exactly the same as calling the echo task directly
    result = run_poe_subproc("also_echo", "foo", esc_prefix + r"${POE_ROOT} !")
    assert (
        result.capture
        == f"Poe => echo POE_ROOT:{dummy_project_path} Password1, task_args: foo {dummy_project_path} !\n"
    )
    assert (
        result.stdout
        == f"POE_ROOT:{dummy_project_path} Password1, task_args: foo {dummy_project_path} !\n"
    )
    assert result.stderr == ""


def test_multiline_non_default_type_task(
    run_poe_subproc, dummy_project_path, esc_prefix
):
    # This should be exactly the same as calling the echo task directly
    result = run_poe_subproc("sing")
    assert result.capture == (
        f'Poe => echo "this is the story";\n'
        'echo "all about how" &&      # the last line won\'t run\n'
        'echo "my life got flipped;\n'
        '  turned upside down" ||\necho "bam bam baaam bam"\n'
    )
    assert result.stdout == (
        f"this is the story\n"
        "all about how\n"
        "my life got flipped;\n"
        "  turned upside down\n"
    )
    assert result.stderr == ""


def test_sequence_task(run_poe_subproc, dummy_project_path, esc_prefix, is_windows):
    result = run_poe_subproc("composite_task")
    if is_windows:
        # On windows shlex works in non-POSIX mode which results in  quotes
        assert (
            result.capture
            == f"Poe => echo 'Hello'\nPoe => echo 'World!'\nPoe => echo ':)!'\n"
        )
        assert result.stdout == f"'Hello'\n'World!'\n':)!'\n"
    else:
        assert (
            result.capture
            == f"Poe => echo Hello\nPoe => echo World!\nPoe => echo :)!\n"
        )
        assert result.stdout == f"Hello\nWorld!\n:)!\n"
    assert result.stderr == ""


def test_another_sequence_task(
    run_poe_subproc, dummy_project_path, esc_prefix, is_windows
):
    # This should be exactly the same as calling the composite_task task directly
    result = run_poe_subproc("also_composite_task")
    if is_windows:
        # On windows shlex works in non-POSIX mode which results in  quotes
        assert (
            result.capture
            == f"Poe => echo 'Hello'\nPoe => echo 'World!'\nPoe => echo ':)!'\n"
        )
        assert result.stdout == f"'Hello'\n'World!'\n':)!'\n"
    else:
        assert (
            result.capture
            == f"Poe => echo Hello\nPoe => echo World!\nPoe => echo :)!\n"
        )
        assert result.stdout == f"Hello\nWorld!\n:)!\n"
    assert result.stderr == ""


def test_a_script_sequence_task(
    run_poe_subproc, dummy_project_path, esc_prefix, is_windows
):
    # This should be exactly the same as calling the composite_task task directly
    result = run_poe_subproc("greet-multiple")
    assert (
        result.capture
        == f"Poe => dummy_package:main('Tom')\nPoe => dummy_package:main('Jerry')\n"
    )
    assert result.stdout == f"hello Tom\nhello Jerry\n"
    assert result.stderr == ""
