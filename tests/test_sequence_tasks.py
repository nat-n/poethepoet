def test_sequence_task(run_poe_subproc, esc_prefix, is_windows):
    result = run_poe_subproc("composite_task", project="sequences")
    assert (
        result.capture
        == f"Poe => poe_test_echo Hello\nPoe => poe_test_echo World!\nPoe => poe_test_echo :)!\n"
    )
    assert result.stdout == f"Hello\nWorld!\n:)!\n"
    assert result.stderr == ""


def test_another_sequence_task(run_poe_subproc, esc_prefix, is_windows):
    # This should be exactly the same as calling the composite_task task directly
    result = run_poe_subproc("also_composite_task", project="sequences")
    assert (
        result.capture
        == f"Poe => poe_test_echo Hello\nPoe => poe_test_echo World!\nPoe => poe_test_echo :)!\n"
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


def test_sequence_task_with_multiple_value_arg(run_poe_subproc):
    result = run_poe_subproc(
        "multiple-value-arg", "hey", "1", "2", "3", project="sequences"
    )
    assert (
        result.capture
        == "Poe => poe_test_echo first: hey\nPoe => poe_test_echo second: 1 2 3\nPoe => poe_test_echo Done.\n"
    )
    assert result.stdout == "first: hey\nsecond: 1 2 3\nDone.\n"
    assert result.stderr == ""
