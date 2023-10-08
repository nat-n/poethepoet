def test_sequence_task(run_poe_subproc, esc_prefix):
    result = run_poe_subproc("composite_task", project="sequences")
    assert result.capture == (
        "Poe => poe_test_echo Hello\n"
        "Poe => poe_test_echo 'World!'\n"
        "Poe => poe_test_echo ':)!'\n"
    )
    assert result.stdout == "Hello\nWorld!\n:)!\n"
    assert result.stderr == ""


def test_another_sequence_task(run_poe_subproc, esc_prefix):
    # This should be exactly the same as calling the composite_task task directly
    result = run_poe_subproc("also_composite_task", project="sequences")
    assert result.capture == (
        "Poe => poe_test_echo Hello\n"
        "Poe => poe_test_echo 'World!'\n"
        "Poe => poe_test_echo ':)!'\n"
    )
    assert result.stdout == "Hello\nWorld!\n:)!\n"
    assert result.stderr == ""


def test_a_script_sequence_task_with_args(run_poe_subproc, esc_prefix):
    # This should be exactly the same as calling the composite_task task directly
    result = run_poe_subproc("greet-multiple", "--mouse=Jerry", project="sequences")
    assert result.capture == (
        """Poe => 'my_package:main(environ.get('"'"'cat'"'"'))'\n"""
        """Poe => 'my_package:main(environ['"'"'mouse'"'"'])'\n"""
    )
    assert result.stdout == "hello Tom\nhello Jerry\n"
    assert result.stderr == ""


def test_sequence_task_with_multiple_value_arg(run_poe_subproc):
    result = run_poe_subproc(
        "multiple-value-arg", "hey", "1", "2", "3", project="sequences"
    )
    assert result.capture == (
        "Poe => poe_test_echo first: hey\nPoe => poe_test_echo second: '1 2 3'\n"
        "Poe => poe_test_echo Done.\n"
    )
    assert result.stdout == "first: hey\nsecond: 1 2 3\nDone.\n"
    assert result.stderr == ""


def test_subtasks_inherit_cwd_option_as_default(run_poe_subproc, is_windows):
    result = run_poe_subproc("all_cwd", project="sequences")
    assert result.capture == (
        "Poe => os.getcwd()\n"
        "Poe => os.getcwd()\n"
        "Poe => 'all_cwd[2]'\n"
        "Poe => 'all_cwd[3]'\n"
    )
    if is_windows:
        assert result.stdout.split()[0].endswith(
            "tests\\fixtures\\sequences_project\\my_package"
        )
        assert result.stdout.split()[1].endswith("tests\\fixtures\\sequences_project")
        assert result.stdout.split()[2].endswith(
            "tests\\fixtures\\sequences_project\\my_package"
        )
        assert result.stdout.split()[3].endswith("tests\\fixtures\\sequences_project")
    else:
        assert result.stdout.split()[0].endswith(
            "tests/fixtures/sequences_project/my_package"
        )
        assert result.stdout.split()[1].endswith("tests/fixtures/sequences_project")
        assert result.stdout.split()[2].endswith(
            "tests/fixtures/sequences_project/my_package"
        )
        assert result.stdout.split()[3].endswith("tests/fixtures/sequences_project")
    assert result.stderr == ""
