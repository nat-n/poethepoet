def test_expr_with_args(run_poe_subproc):
    result = run_poe_subproc("expr_with_args", project="expr")
    assert result.capture == (
        """Poe => "power level is " + (f"only {power_level}" """
        """if int(${power_level}) <= 9000 else 'over nine thousand!\')\n"""
    )
    assert result.stdout == "power level is only 42\n"
    assert result.stderr == ""

    result = run_poe_subproc("expr_with_args", "999", project="expr")
    assert result.capture == (
        """Poe => "power level is " + (f"only {power_level}" """
        """if int(${power_level}) <= 9000 else 'over nine thousand!\')\n"""
    )
    assert result.stdout == "power level is only 999\n"
    assert result.stderr == ""

    result = run_poe_subproc("expr_with_args", "9001", project="expr")
    assert result.capture == (
        """Poe => "power level is " + (f"only {power_level}" """
        """if int(${power_level}) <= 9000 else 'over nine thousand!\')\n"""
    )
    assert result.stdout == "power level is over nine thousand!\n"
    assert result.stderr == ""


def test_expr_with_argv(run_poe_subproc):
    result = run_poe_subproc("expr_with_argv", "999", project="expr")
    assert result.capture == (
        """Poe => "power level is " + (f"only {sys.argv[1]}" """
        """if int(sys.argv[1]) <= 9000 else 'over nine thousand!\')\n"""
    )
    assert result.stdout == "power level is only 999\n"
    assert result.stderr == ""

    result = run_poe_subproc("expr_with_argv", "9001", project="expr")
    assert result.capture == (
        """Poe => "power level is " + (f"only {sys.argv[1]}" """
        """if int(sys.argv[1]) <= 9000 else 'over nine thousand!\')\n"""
    )
    assert result.stdout == "power level is over nine thousand!\n"
    assert result.stderr == ""


def test_expr_with_env_vars(run_poe_subproc):
    result = run_poe_subproc(
        "expr_with_env_vars",
        "999",
        project="expr",
        env={"VAR_FOO": "foo", "VAR_BAR": "2", "VAR_BAZ": "boo"},
    )
    assert result.capture == (
        "Poe => [${VAR_FOO} * int(${VAR_BAR})][0] + (f'{${VAR_BAZ}}')"
        " + '${NOTHING}'\n"
    )
    assert result.stdout == "foofooboo\n"
    assert result.stderr == ""


def test_expr_with_imports(run_poe_subproc):
    result = run_poe_subproc("expr_with_imports", project="expr")
    assert result.capture == "Poe => bool(re.match(r'^\\S+@\\S+\\.\\S+$', ${EMAIL}))\n"
    assert result.stdout == "True\n"
    assert result.stderr == ""

    result = run_poe_subproc("expr_with_imports", project="expr", env={"EMAIL": "lol"})
    assert result.capture == "Poe => bool(re.match(r'^\\S+@\\S+\\.\\S+$', ${EMAIL}))\n"
    assert result.stdout == "False\n"
    assert result.stderr == ""


def test_expr_with_assert(run_poe_subproc):
    result = run_poe_subproc("expr_with_assert", "-2", project="expr")
    assert result.capture == "Poe => min_value < 3\n"
    assert result.stdout == "True\n"
    assert result.stderr == ""
    assert result.code == 0

    result = run_poe_subproc("expr_with_assert", "4", project="expr")
    assert result.capture == "Poe => min_value < 3\n"
    assert result.stdout == "False\n"
    assert result.stderr == ""
    assert result.code == 1


def test_expr_with_uses(run_poe_subproc):
    result = run_poe_subproc("expr_with_uses", project="expr")
    assert result.capture == (
        "Poe <= 0\n"
        "Poe => f'There have been {${GOOD_DAYS}} since the last failed test.'\n"
    )
    assert result.stdout == "There have been 0 since the last failed test.\n"
    assert result.stderr == ""
    assert result.code == 0


def test_christmas_tree_expr(run_poe_subproc):
    result = run_poe_subproc("christmas_tree_expr", project="expr")

    # capture is a bit complicated, not that interesting
    assert result.stdout == "True\n"
    assert result.stderr == ""
    assert result.code == 0
