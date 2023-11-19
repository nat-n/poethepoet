import sys


def test_switch_on_platform(run_poe_subproc):
    common_prefix = "Poe <= override or sys.platform\n"
    result = run_poe_subproc("platform_dependent", project="switch")

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


def test_switch_on_override_arg(run_poe_subproc):
    common_prefix = "Poe <= override or sys.platform\n"
    result = run_poe_subproc("platform_dependent", "--override=Ti83", project="switch")
    assert result.capture == (
        f"{common_prefix}Poe => import sys; "
        "print('Looks like you are running some exotic OS.')\n"
    )
    assert result.stdout == "Looks like you are running some exotic OS.\n"
    assert result.stderr == ""


def test_switch_on_env_var(run_poe_subproc):
    common_prefix = "Poe <= int(${FOO_VAR}) % 2\n"
    result = run_poe_subproc("var_dependent", project="switch", env={"FOO_VAR": "42"})
    assert result.capture == common_prefix + "Poe => f'{${FOO_VAR}} is even'\n"
    assert result.stdout == "42 is even\n"
    assert result.stderr == ""

    result = run_poe_subproc("var_dependent", project="switch", env={"FOO_VAR": "99"})
    assert result.capture == (
        f"{common_prefix}Poe => import sys, os; "
        "print(os.environ['FOO_VAR'], 'is odd')\n"
    )
    assert result.stdout == "99 is odd\n"
    assert result.stderr == ""


def test_switch_default_pass(run_poe_subproc):
    result = run_poe_subproc("default_pass", project="switch")
    assert result.capture == "Poe <= poe_test_echo nothing\n"
    assert result.stdout == ""
    assert result.stderr == ""


def test_switch_default_fail(run_poe_subproc):
    result = run_poe_subproc("default_fail", project="switch")
    assert result.capture == (
        "Poe <= poe_test_echo nothing\n"
        "Error: Control value 'nothing' did not match any cases in switch task "
        "'default_fail'.\n"
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_switch_dry_run(run_poe_subproc):
    result = run_poe_subproc("-d", "var_dependent", project="switch")
    assert result.capture == (
        "Poe <= int(${FOO_VAR}) % 2\n" "Poe ?? unresolved case for switch task\n"
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_switch_in_in_graph(run_poe_subproc):
    result = run_poe_subproc("switcher_user", project="switch")
    assert result.capture == (
        "Poe <= 42\n" "Poe <= echo matched\n" "Poe => echo switched=matched\n"
    )
    assert result.stdout == "switched=matched\n"
    assert result.stderr == ""


def test_switch_multivalue_case(run_poe_subproc):
    for num in ("1", "3", "5"):
        result = run_poe_subproc(
            "multivalue_case", project="switch", env={"WHATEVER": num}
        )
        assert result.capture == (
            f"Poe <= poe_test_echo {num}\nPoe => import sys; print('It is in 1-5')\n"
        )
        assert result.stdout == "It is in 1-5\n"
        assert result.stderr == ""

    result = run_poe_subproc("multivalue_case", project="switch", env={"WHATEVER": "6"})
    assert result.capture == (
        "Poe <= poe_test_echo 6\nPoe => import sys; print('It is 6')\n"
    )
    assert result.stdout == "It is 6\n"
    assert result.stderr == ""

    result = run_poe_subproc("multivalue_case", project="switch", env={"WHATEVER": "7"})
    assert result.capture == (
        "Poe <= poe_test_echo 7\nPoe => import sys; print('It is not in 1-6')\n"
    )
    assert result.stdout == "It is not in 1-6\n"
    assert result.stderr == ""


def test_switch_capture_out(run_poe_subproc, projects):
    result = run_poe_subproc("capture_out", project="switch")
    assert result.capture == ("Poe <= 43\n" "Poe <= echo default\n")
    assert result.stdout == ""
    assert result.stderr == ""

    output_path = projects["switch"].joinpath("out.txt")
    try:
        with output_path.open("r") as output_file:
            assert output_file.read() == "default\n"
    finally:
        output_path.unlink()
