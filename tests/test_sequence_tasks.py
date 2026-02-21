import pytest


def test_sequence_task(run_poe_subproc, esc_prefix):
    result = run_poe_subproc("composite_task", project="sequences")
    assert result.capture == (
        "Poe => poe_test_echo Hello\n"
        "Poe => poe_test_echo 'World!'\n"
        "Poe => poe_test_echo ':)!'\n"
    )
    assert result.stdout == "Hello\nWorld!\n:)!\n"
    assert result.stderr == ""


@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_list_inside_sequence_is_parallel(run_poe_subproc, esc_prefix, delay_factor):
    base = 50 * delay_factor
    d0, d1, d2 = 0, base, 2 * base
    result = run_poe_subproc(
        "sequential_parallel",
        str(d0),
        str(d1),
        str(d2),
        project="sequences",
        env={"NO_COLOR": "1"},
    )
    assert result.capture == (
        "Poe => poe_test_echo First\n"
        f"Poe => poe_test_delayed_echo {d1} second {d1}\n"
        f"Poe => poe_test_delayed_echo {d0} second {d0}\n"
        f"Poe => poe_test_delayed_echo {d2} second {d2}\n"
        f"Poe => poe_test_delayed_echo {d1} third {d1}\n"
        f"Poe => poe_test_delayed_echo {d0} third {d0}\n"
        f"Poe => poe_test_delayed_echo {d2} third {d2}\n"
        "Poe => poe_test_echo Last\n"
    )
    assert result.stdout == (
        "First\n"
        f"sequential_para… | second {d0}\n"
        f"sequential_para… | second {d1}\n"
        f"sequential_para… | second {d2}\n"
        f"sequential_para… | third {d0}\n"
        f"sequential_para… | third {d1}\n"
        f"sequential_para… | third {d2}\n"
        "Last\n"
    )
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
