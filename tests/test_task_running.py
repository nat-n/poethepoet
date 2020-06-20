import pytest


def test_call_echo_task(run_poe_subproc, dummy_project_path):
    # The $ has to be escaped or it'll be evaluated by the outer shell and poe will
    # never see it
    result = run_poe_subproc("echo", "foo", r"\${POE_ROOT} !")
    assert (
        result.capture
        == f"Poe => echo POE_ROOT:{dummy_project_path} task_args: foo {dummy_project_path} !\n"
    )
    assert (
        result.stdout
        == f"POE_ROOT:{dummy_project_path} task_args: foo {dummy_project_path} !\n"
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
    input_var, output_var, run_poe_subproc, dummy_project_path
):
    # A further (outer shell escaped) escape can be added to indicate to POE that the $
    # is escaped
    # For the sake of sanity poe leaves the remaining backslashes alone
    result = run_poe_subproc("echo", input_var, "!")
    output_var_ = output_var.replace("dummy_project_path", str(dummy_project_path))
    assert (
        result.capture
        == f"Poe => echo POE_ROOT:{dummy_project_path} task_args: {output_var_} !\n"
    )
    # assert result.stdout == f"POE_ROOT:{dummy_project_path} task_args: {output_var} !\n"
    assert result.stderr == ""


def test_shell_task(run_poe_subproc, dummy_project_path):
    result = run_poe_subproc("count")
    assert (
        result.capture
        == f"Poe => echo 1 && echo 2 && echo $(python -c 'print(1 + 2)')\n"
    )
    assert result.stdout == "1\n2\n3\n"
    assert result.stderr == ""


def test_script_task(run_poe_subproc, dummy_project_path):
    # The $ has to be escaped or it'll be evaluated by the outer shell and poe will
    # never see it
    result = run_poe_subproc("greet", "nat,", r"welcome to \${POE_ROOT}")
    assert result.capture == f"Poe => greet nat, welcome to {dummy_project_path}\n"
    assert result.stdout == f"hello nat, welcome to {dummy_project_path}\n"
    assert result.stderr == ""
