import sys

import pytest


def test_switch_on_platform(run_poe):
    common_prefix = "Poe <= override or sys.platform\n"
    result = run_poe("platform_dependent", project="switch")

    if sys.platform == "win32":
        assert (
            result.capture
            == f"{common_prefix}Poe => import sys; print('You are on windows.')\n"
        )
        assert result.stdout == "You are on windows.\n"

    elif sys.platform == "linux":
        assert (
            result.capture
            == f"{common_prefix}Poe => import sys; print('You are on linux.')\n"
        )
        assert result.stdout == "You are on linux.\n"

    elif sys.platform == "darwin":
        assert result.capture == f"{common_prefix}Poe => 'You are on a mac.'\n"
        assert result.stdout == "You are on a mac.\n"

    else:
        assert result.capture == (
            f"{common_prefix}Poe => import sys; "
            "print('Looks like you are running some exotic OS.')\n"
        )
        assert result.stdout == "Looks like you are running some exotic OS.\n"

    assert result.stderr == ""


def test_switch_on_override_arg(run_poe):
    common_prefix = "Poe <= override or sys.platform\n"
    result = run_poe("platform_dependent", "--override=Ti83", project="switch")
    assert result.capture == (
        f"{common_prefix}Poe => import sys; "
        "print('Looks like you are running some exotic OS.')\n"
    )
    assert result.stdout == "Looks like you are running some exotic OS.\n"
    assert result.stderr == ""


def test_switch_on_env_var(run_poe):
    common_prefix = "Poe <= int(${FOO_VAR}) % 2\n"
    result = run_poe("var_dependent", project="switch", env={"FOO_VAR": "42"})
    assert result.capture == common_prefix + "Poe => f'{${FOO_VAR}} is even'\n"
    assert result.stdout == "42 is even\n"
    assert result.stderr == ""

    result = run_poe("var_dependent", project="switch", env={"FOO_VAR": "99"})
    assert result.capture == (
        f"{common_prefix}Poe => import sys, os; "
        "print(os.environ['FOO_VAR'], 'is odd')\n"
    )
    assert result.stdout == "99 is odd\n"
    assert result.stderr == ""


def test_switch_default_pass(run_poe):
    result = run_poe("default_pass", project="switch")
    assert result.capture == "Poe <= poe_test_echo nothing\n"
    assert result.stdout == ""
    assert result.stderr == ""


def test_switch_default_fail(run_poe):
    result = run_poe("default_fail", project="switch")
    assert result.capture == (
        "Poe <= poe_test_echo nothing\n"
        "Error: Control value 'nothing' did not match any cases in switch task "
        "'default_fail'.\n"
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_switch_dry_run(run_poe):
    result = run_poe("-d", "var_dependent", project="switch")
    assert result.capture == (
        "Poe <= int(${FOO_VAR}) % 2\nPoe ?? unresolved case for switch task\n"
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_switch_in_in_graph(run_poe):
    result = run_poe("switcher_user", project="switch")
    assert result.capture == (
        "Poe <= 42\nPoe <= echo matched\nPoe => echo switched=matched\n"
    )
    assert result.stdout == "switched=matched\n"
    assert result.stderr == ""


def test_switch_multivalue_case(run_poe):
    for num in ("1", "3", "5"):
        result = run_poe("multivalue_case", project="switch", env={"WHATEVER": num})
        assert result.capture == (
            f"Poe <= poe_test_echo {num}\nPoe => import sys; print('It is in 1-5')\n"
        )
        assert result.stdout == "It is in 1-5\n"
        assert result.stderr == ""

    result = run_poe("multivalue_case", project="switch", env={"WHATEVER": "6"})
    assert result.capture == (
        "Poe <= poe_test_echo 6\nPoe => import sys; print('It is 6')\n"
    )
    assert result.stdout == "It is 6\n"
    assert result.stderr == ""

    result = run_poe("multivalue_case", project="switch", env={"WHATEVER": "7"})
    assert result.capture == (
        "Poe <= poe_test_echo 7\nPoe => import sys; print('It is not in 1-6')\n"
    )
    assert result.stdout == "It is not in 1-6\n"
    assert result.stderr == ""


def test_switch_capture_out(run_poe, projects):
    result = run_poe("capture_out", project="switch")
    assert result.capture == ("Poe <= 43\nPoe <= echo default\n")
    assert result.stdout == ""
    assert result.stderr == ""

    output_path = projects["switch"].joinpath("out.txt")
    try:
        with output_path.open("r") as output_file:
            assert output_file.read() == "default\n"
    finally:
        output_path.unlink()


@pytest.mark.parametrize(
    ("task", "cli_args", "expected_stdout_tail"),
    [
        pytest.param(
            "booleans-cmd",
            (),
            """case=True
${non}= ${non:+plus}= ${non:-minus}=minus
${fal}= ${fal:+plus}= ${fal:-minus}=minus
${tru}=True ${tru:+plus}=plus ${tru:-minus}=True
${txt}=True ${txt:+plus}=plus ${txt:-minus}=True
""",
            id="cmd_defaults_match_True_arm",
        ),
        pytest.param(
            "booleans-cmd",
            ("--non", "--tru", "--fal", "--txt"),
            "{'non': True, 'tru': False, 'fal': True, 'txt': False}\n",
            id="cmd_toggled_falls_through_to_default_expr_arm",
        ),
        pytest.param(
            "booleans-expr",
            (),
            "{'case': True, 'non': False, 'tru': True, 'fal': False, 'txt': True}\n",
            id="expr_defaults_match_True_arm",
        ),
        pytest.param(
            "booleans-expr",
            ("--non", "--tru", "--fal", "--txt"),
            """${non}=True ${non:+plus}=plus ${non:-minus}=True
${fal}=True ${fal:+plus}=plus ${fal:-minus}=True
${tru}= ${tru:+plus}= ${tru:-minus}=minus
${txt}= ${txt:+plus}= ${txt:-minus}=minus
""",
            id="expr_toggled_falls_through_to_default_cmd_arm",
        ),
    ],
)
def test_switch_boolean_flag(
    run_poe, task: str, cli_args: tuple[str, ...], expected_stdout_tail: str
) -> None:
    """
    Switch task control: the control task's resolved value selects which
    branch runs. For booleans-cmd the control is a cmd echoing ${txt:-minus}
    (matches the "True" arm when txt's truthy default is preserved, else
    falls through). For booleans-expr the control evaluates the tru var
    (same pattern via the True/False bool stringified to "True"/"False").
    Each case asserts the tail of stdout from the selected branch.
    """
    result = run_poe(task, *cli_args, project="switch")
    assert result.stdout.endswith(expected_stdout_tail)


def test_switch_task_forwards_extra_args_via_poe_extra_args(run_poe):
    """Switch task forwards free args to selected branch via POE_EXTRA_ARGS"""
    result = run_poe("echo-extra-branch", "foo", "bar", project="switch")
    assert result.capture == (
        "Poe <= poe_test_echo match\nPoe => poe_test_echo matched: foo bar\n"
    )
    assert result.stdout == "matched: foo bar\n"
    assert result.stderr == ""


def test_switch_task_forwards_extra_args_with_trailing_args(run_poe):
    """$POE_EXTRA_ARGS in a switch branch can have args both before and after"""
    result = run_poe("echo-extra-branch-trailing", "foo", "bar", project="switch")
    assert result.capture == (
        "Poe <= poe_test_echo match\nPoe => poe_test_echo before: foo bar :after\n"
    )
    assert result.stdout == "before: foo bar :after\n"
    assert result.stderr == ""


def test_switch_case_may_not_declare_uses_env(temp_pyproject, run_poe):
    """A switch case may not redeclare uses_env, like uses and deps"""
    project_path = temp_pyproject("""
        [tool.poe.tasks._producer]
        cmd = "poe_test_echo_lines X=1"

        [tool.poe.tasks.sw]
        control.cmd = "poe_test_echo a"

        [[tool.poe.tasks.sw.switch]]
        case = "a"
        cmd = "poe_test_echo hi"
        uses_env = "_producer"
        """)
    result = run_poe("sw", cwd=project_path)
    assert "Error: Invalid task 'sw'" in result.capture
    assert "Case 'a' includes incompatible option 'uses_env'" in result.capture
    assert result.stdout == ""


@pytest.mark.parametrize(
    ("cli_args", "expected"),
    [((), "loud=\n"), (("--loud",), "loud=True\n")],
)
def test_switch_case_boolean_arg_with_self_referencing_default(
    temp_pyproject, run_poe, cli_args, expected
):
    """
    Case tasks resolve the switch's args against the env as the switch found it, so
    a default referencing the arg's own variable can't see the switch's value for it
    """
    project_path = temp_pyproject("""
        [tool.poe.tasks.sw]
        control.expr = "'x'"
        switch = [{ case = "x", cmd = "poe_test_echo loud=${loud}" }]
        args = [{ name = "loud", type = "boolean", default = "${loud}" }]
        """)
    result = run_poe("sw", *cli_args, cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == expected


@pytest.mark.parametrize(
    ("cli_args", "expected"),
    [((), "loud=no\n"), (("--loud",), "loud=yes\n")],
)
def test_switch_case_boolean_arg_with_custom_strings(
    temp_pyproject, run_poe, cli_args, expected
):
    project_path = temp_pyproject("""
        [tool.poe.tasks.sw]
        control.expr = "'x'"
        switch = [{ case = "x", cmd = "poe_test_echo loud=${loud}" }]

        [[tool.poe.tasks.sw.args]]
        name = "loud"
        type = "boolean"
        default = "${loud}"
        true_string = "yes"
        false_string = "no"
        """)
    result = run_poe("sw", *cli_args, cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == expected


def test_switch_case_arg_defaults_match_the_switch(temp_pyproject, run_poe):
    """
    A default referencing another arg of the same task can't see that arg's value,
    and a switch case resolves it the same way as the switch itself
    """
    project_path = temp_pyproject("""
        [tool.poe.tasks.sw]
        control.expr = "f'{region}/{bucket}'"
        switch = [{ case = "us/none-bucket", cmd = "poe_test_echo bucket=${bucket}" }]
        args = [
            { name = "region", default = "eu" },
            { name = "bucket", default = "${region:-none}-bucket" },
        ]
        """)
    result = run_poe("sw", "--region", "us", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout.endswith("bucket=none-bucket\n")


def test_switch_case_module_script_receives_args(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.sw]
        control.expr = "'x'"
        switch = [{ case = "x", script = "probe" }]
        args = [
            { name = "size", type = "integer", default = 1 },
            { name = "loud", type = "boolean" },
        ]
        """)
    (project_path / "probe.py").write_text("import sys\nprint(sys.argv[1:])\n")
    result = run_poe("sw", "--size", "3", "--loud", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout.endswith("['--size', '3', '--loud']\n")


@pytest.mark.parametrize(
    ("case_task", "expected_error"),
    [
        (
            'cmd = "poe_test_echo *.nomatch"\nempty_glob = "fail"',
            "Error: Glob pattern '*.nomatch' did not match any files",
        ),
        ("expr = \"f'{1} is even')\"", "Error: Invalid expr content: f'{1} is even')"),
    ],
    ids=["execution_error", "invalid_expr"],
)
def test_switch_case_error_propagates(
    temp_pyproject, run_poe, case_task, expected_error
):
    """
    An error raised while running the selected case task fails the switch with the
    case's error message
    """
    project_path = temp_pyproject(f"""
        [tool.poe.tasks.sw]
        control.expr = "'a'"

        [[tool.poe.tasks.sw.switch]]
        case = "a"
        {case_task}
        """)
    result = run_poe("sw", cwd=project_path)
    assert result.code == 1, result.capture
    assert expected_error in result.capture


def test_switch_control_task_verbosity(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.sw]
        control = { expr = "'a'", verbosity = -1 }
        switch = [{ case = "a", cmd = "poe_test_echo A" }]
        """)
    result = run_poe("sw", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.capture == "Poe => poe_test_echo A\n"
    assert result.stdout == "A\n"
