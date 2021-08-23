def test_sequence_task(run_poe_subproc, esc_prefix, is_windows):
    result = run_poe_subproc("composite_task", project="sequences")
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


def test_another_sequence_task(run_poe_subproc, esc_prefix, is_windows):
    # This should be exactly the same as calling the composite_task task directly
    result = run_poe_subproc("also_composite_task", project="sequences")
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


def test_a_script_sequence_task_with_args(run_poe_subproc, esc_prefix):
    # This should be exactly the same as calling the composite_task task directly
    result = run_poe_subproc("greet-multiple", "--mouse=Jerry", project="sequences")
    assert (
        result.capture
        == f"Poe => my_package:main(environ.get('cat'))\nPoe => my_package:main(environ['mouse'])\n"
    )
    assert result.stdout == f"hello Tom\nhello Jerry\n"
    assert result.stderr == ""
