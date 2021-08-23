def test_call_echo_task(run_poe_subproc, projects, esc_prefix):
    # The $ has to be escaped or it'll be evaluated by the outer shell and poe will
    # never see it
    result = run_poe_subproc("echo", "foo", "!")
    assert (
        result.capture
        == f"Poe => echo POE_ROOT:{projects['example']} Password1, task_args: foo !\n"
    )
    assert (
        result.stdout == f"POE_ROOT:{projects['example']} Password1, task_args: foo !\n"
    )
    assert result.stderr == ""


def test_setting_envvar_in_task(run_poe_subproc, projects):
    # The $ has to be escaped or it'll be evaluated by the outer shell and poe will
    # never see it
    result = run_poe_subproc("show_env")
    assert result.capture == f"Poe => env\n"
    assert f"POE_ROOT={projects['example']}" in result.stdout
    assert result.stderr == ""


def test_sequence_task(run_poe_subproc, esc_prefix, is_windows):
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
