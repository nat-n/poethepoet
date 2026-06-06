import pytest


def test_sequence_task(run_poe, esc_prefix):
    result = run_poe("composite_task", project="sequences")
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


def test_a_script_sequence_task_with_args(run_poe, esc_prefix):
    # This should be exactly the same as calling the composite_task task directly
    result = run_poe("greet-multiple", "--mouse=Jerry", project="sequences")
    assert result.capture == (
        """Poe => 'my_package:main(environ.get('"'"'cat'"'"'))'\n"""
        """Poe => 'my_package:main(environ['"'"'mouse'"'"'])'\n"""
    )
    assert result.stdout == "hello Tom\nhello Jerry\n"
    assert result.stderr == ""


def test_sequence_task_with_multiple_value_arg(run_poe):
    result = run_poe("multiple-value-arg", "hey", "1", "2", "3", project="sequences")
    assert result.capture == (
        "Poe => poe_test_echo first: hey\nPoe => poe_test_echo second: '1 2 3'\n"
        "Poe => poe_test_echo Done.\n"
    )
    assert result.stdout == "first: hey\nsecond: 1 2 3\nDone.\n"
    assert result.stderr == ""


def test_subtasks_inherit_cwd_option_as_default(run_poe, is_windows):
    result = run_poe("all_cwd", project="sequences")
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


@pytest.mark.parametrize(
    ("cli_args", "cmd_shell_lines", "expr_dict"),
    [
        pytest.param(
            (),
            """${non}= ${non:+plus}= ${non:-minus}=minus
${fal}= ${fal:+plus}= ${fal:-minus}=minus
${tru}=True ${tru:+plus}=plus ${tru:-minus}=True
${txt}=True ${txt:+plus}=plus ${txt:-minus}=True
""",
            "{'non': False, 'tru': True, 'fal': False, 'txt': True}",
            id="defaults",
        ),
        pytest.param(
            ("--non", "--tru", "--fal", "--txt"),
            """${non}=True ${non:+plus}=plus ${non:-minus}=True
${fal}=True ${fal:+plus}=plus ${fal:-minus}=True
${tru}= ${tru:+plus}= ${tru:-minus}=minus
${txt}= ${txt:+plus}= ${txt:-minus}=minus
""",
            "{'non': True, 'tru': False, 'fal': True, 'txt': False}",
            id="all_toggled",
        ),
    ],
)
def test_sequences_boolean_flag(
    run_poe,
    cli_args: tuple[str, ...],
    cmd_shell_lines: str,
    expr_dict: str,
) -> None:
    """
    Boolean args propagate consistently through a sequence's cmd + shell +
    expr subtasks: the cmd and shell subtasks both see the resolved values
    via env vars (``"True"``/unset), and the expr subtask sees them as real
    Python bools.
    """
    result = run_poe("booleans", *cli_args, project="sequences")
    expected_tail = f"{cmd_shell_lines}{cmd_shell_lines}{expr_dict}\n"
    assert result.stdout.endswith(expected_tail)


def test_private_env_inherited_and_filtered(run_poe, is_windows):
    """Private vars remain private when inherited by subtasks in a sequence"""
    result = run_poe("private_inherited", project="sequences")
    stdout_lower = result.stdout.lower()
    if not is_windows:
        assert "_secret=hidden" not in result.stdout
    assert "normal=visible" in stdout_lower


def test_private_env_inherited_can_be_remapped_public(run_poe, is_windows):
    """A child task can alias inherited private env vars to public names via env"""
    result = run_poe("private_env_remapped", project="sequences")
    stdout_lower = result.stdout.lower()
    if not is_windows:
        assert "_secret=hidden" not in result.stdout
    assert "public=hidden" in stdout_lower


def test_private_arg_inherited_and_filtered(run_poe, is_windows):
    """Private args inherited by a child stay hidden from the subprocess env"""
    result = run_poe("private_arg_inherited", project="sequences")
    stdout_lower = result.stdout.lower()
    if not is_windows:
        assert "_secret=hidden" not in result.stdout
    assert "public=visible" in stdout_lower


def test_private_arg_inherited_can_be_remapped_public(run_poe, is_windows):
    """A child task can alias inherited private args to public env vars via env"""
    result = run_poe("private_arg_remapped", project="sequences")
    stdout_lower = result.stdout.lower()
    if not is_windows:
        assert "_secret=hidden" not in result.stdout
    assert "public=hidden" in stdout_lower


def test_sequence_task_forwards_extra_args_via_poe_extra_args_in_ref(run_poe):
    """Extra args passed to a sequence task are forwarded via $POE_EXTRA_ARGS in ref"""
    result = run_poe("extra-args-via-ref", "hello", "world", project="sequences")
    assert result.capture == (
        "Poe => poe_test_echo hello world\nPoe => poe_test_echo done\n"
    )
    assert result.stdout == "hello world\ndone\n"
    assert result.stderr == ""


def test_sequence_task_forwards_extra_args_via_poe_extra_args_env(run_poe):
    """Inline subtasks can access POE_EXTRA_ARGS set by the parent sequence task"""
    result = run_poe("extra-args-via-env", "hello", "world", project="sequences")
    assert result.capture == (
        "Poe => poe_test_echo hello world\nPoe => poe_test_echo done\n"
    )
    assert result.stdout == "hello world\ndone\n"
    assert result.stderr == ""


def test_sequence_task_forwards_extra_args_with_trailing_args(run_poe):
    """$POE_EXTRA_ARGS in a sequence subtask can have args both before and after"""
    result = run_poe("extra-args-trailing", "hello", "world", project="sequences")
    assert result.capture == (
        "Poe => poe_test_echo before hello world after\nPoe => poe_test_echo done\n"
    )
    assert result.stdout == "before hello world after\ndone\n"
    assert result.stderr == ""
