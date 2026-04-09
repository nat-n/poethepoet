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


def test_sequences_boolean_flag(run_poe):
    result = run_poe(
        "booleans",
        "--non",
        "--tru",
        "--fal",
        "--txt",
        project="sequences",
    )
    assert result.capture == (
        r"""Poe => poe_test_echo '
${non}=True' '${non:+plus}=plus' '${non:-minus}=True
${fal}=True' '${fal:+plus}=plus' '${fal:-minus}=True
${tru}=' '${tru:+plus}=' '${tru:-minus}=minus
${txt}=' '${txt:+plus}=' '${txt:-minus}=minus'
"""
        r"Poe => poe_test_echo "
        r"""\${non}=${non} \${non:+plus}=${non:+plus} \${non:-minus}=${non:-minus}
poe_test_echo \${fal}=${fal} \${fal:+plus}=${fal:+plus} \${fal:-minus}=${fal:-minus}
poe_test_echo \${tru}=${tru} \${tru:+plus}=${tru:+plus} \${tru:-minus}=${tru:-minus}
poe_test_echo \${txt}=${txt} \${txt:+plus}=${txt:+plus} \${txt:-minus}=${txt:-minus}
"""
        "Poe => {'non':non, 'tru':tru, 'fal':fal, 'txt':txt}\n"
    )
    # Verify cmd and shell subtasks see boolean values via env vars
    assert result.stdout.endswith(
        """
${non}=True ${non:+plus}=plus ${non:-minus}=True
${fal}=True ${fal:+plus}=plus ${fal:-minus}=True
${tru}= ${tru:+plus}= ${tru:-minus}=minus
${txt}= ${txt:+plus}= ${txt:-minus}=minus
${non}=True ${non:+plus}=plus ${non:-minus}=True
${fal}=True ${fal:+plus}=plus ${fal:-minus}=True
${tru}= ${tru:+plus}= ${tru:-minus}=minus
${txt}= ${txt:+plus}= ${txt:-minus}=minus
{'non': True, 'tru': False, 'fal': True, 'txt': False}
""".lstrip()
    )


def test_sequences_boolean_flag_default_value(run_poe):
    result = run_poe("booleans", project="sequences")
    assert result.capture == (
        r"""Poe => poe_test_echo '
${non}=' '${non:+plus}=' '${non:-minus}=minus
${fal}=' '${fal:+plus}=' '${fal:-minus}=minus
${tru}=True' '${tru:+plus}=plus' '${tru:-minus}=True
${txt}=text' '${txt:+plus}=plus' '${txt:-minus}=text'
"""
        r"Poe => poe_test_echo "
        r"""\${non}=${non} \${non:+plus}=${non:+plus} \${non:-minus}=${non:-minus}
poe_test_echo \${fal}=${fal} \${fal:+plus}=${fal:+plus} \${fal:-minus}=${fal:-minus}
poe_test_echo \${tru}=${tru} \${tru:+plus}=${tru:+plus} \${tru:-minus}=${tru:-minus}
poe_test_echo \${txt}=${txt} \${txt:+plus}=${txt:+plus} \${txt:-minus}=${txt:-minus}
"""
        "Poe => {'non':non, 'tru':tru, 'fal':fal, 'txt':txt}\n"
    )
    # Verify cmd and shell subtasks see boolean values via env vars
    assert result.stdout.endswith(
        """
${non}= ${non:+plus}= ${non:-minus}=minus
${fal}= ${fal:+plus}= ${fal:-minus}=minus
${tru}=True ${tru:+plus}=plus ${tru:-minus}=True
${txt}=text ${txt:+plus}=plus ${txt:-minus}=text
${non}= ${non:+plus}= ${non:-minus}=minus
${fal}= ${fal:+plus}= ${fal:-minus}=minus
${tru}=True ${tru:+plus}=plus ${tru:-minus}=True
${txt}=text ${txt:+plus}=plus ${txt:-minus}=text
{'non': False, 'tru': True, 'fal': False, 'txt': 'text'}
""".lstrip()
    )


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


def test_sequence_forwards_free_args(run_poe_subproc):
    result = run_poe_subproc(
        "forward-free-args-seq", "extra1", "extra2", project="sequences"
    )
    assert result.capture == (
        "Poe => poe_test_echo one two extra1 extra2\n"
        "Poe => poe_test_echo one two extra1 extra2\n"
    )
    assert result.stdout == "one two extra1 extra2\none two extra1 extra2\n"
    assert result.stderr == ""


def test_sequence_with_named_args_forwards_free_args(run_poe_subproc):
    result = run_poe_subproc(
        "forward-free-args-seq-with-named",
        "hi",
        "--",
        "extra1",
        "extra2",
        project="sequences",
    )
    assert result.capture == (
        "Poe => poe_test_echo one two extra1 extra2\n"
        "Poe => poe_test_echo one two extra1 extra2\n"
    )
    assert result.stdout == "one two extra1 extra2\none two extra1 extra2\n"
    assert result.stderr == ""
