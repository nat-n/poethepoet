import pytest


def test_call_echo_task(run_poe_subproc, dummy_project_path):
    # The $ has to be escaped or it'll be evaluated by the outer shell and poe will
    # never see it
    result = run_poe_subproc("echo", "foo", "\${POE_ROOT} !")
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
