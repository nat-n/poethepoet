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
        "Poe => [${VAR_FOO} * int(${VAR_BAR})][0] + (f'{${VAR_BAZ}}') + '${NOTHING}'\n"
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


def test_expr_boolean_flag(run_poe_subproc):
    result = run_poe_subproc(
        "booleans", "--non", "--tru", "--fal", "--txt", project="expr"
    )
    assert result.capture == "Poe => {'non':non, 'tru':tru, 'fal':fal, 'txt':txt}\n"
    assert result.stdout == "{'non': True, 'tru': False, 'fal': True, 'txt': False}\n"


def test_expr_boolean_flag_default_value(run_poe_subproc):
    result = run_poe_subproc("booleans", project="expr")
    assert result.capture == "Poe => {'non':non, 'tru':tru, 'fal':fal, 'txt':txt}\n"
    assert result.stdout == "{'non': False, 'tru': True, 'fal': False, 'txt': 'text'}\n"


def test_expr_boolean_flag_partial(run_poe_subproc):
    """--non toggles False->True, --tru negates True->False, fal/txt keep defaults"""
    result = run_poe_subproc("booleans", "--non", "--tru", project="expr")
    assert result.capture == "Poe => {'non':non, 'tru':tru, 'fal':fal, 'txt':txt}\n"
    assert result.stdout == "{'non': True, 'tru': False, 'fal': False, 'txt': 'text'}\n"


def test_expr_multi_value_typed_list(run_poe_subproc):
    """Expr tasks receive multiple args as typed Python lists"""
    result = run_poe_subproc(
        "multi_value_expr", "--nums", "1", "2", "3", "--words", "a", "b", project="expr"
    )
    assert result.stdout == "{'nums': [1, 2, 3], 'words': ['a', 'b']}\n"


def test_expr_multi_value_not_provided(run_poe_subproc):
    """Multiple args not provided: expr sees None (argparse default)"""
    result = run_poe_subproc("multi_value_expr", project="expr")
    assert result.stdout == "{'nums': None, 'words': None}\n"


def test_expr_multi_value_empty_flag(run_poe_subproc):
    """Multiple args provided with no values (--nums --words): expr sees empty lists"""
    result = run_poe_subproc("multi_value_expr", "--nums", "--words", project="expr")
    assert result.stdout == "{'nums': [], 'words': []}\n"


def test_expr_private_arg_accessible(run_poe_subproc):
    """Private args are accessible as typed values in expr tasks"""
    result = run_poe_subproc("private_arg_expr", project="expr")
    assert result.stdout == "{'_flag': True, '_FLAG': True}\n"


def test_expr_private_arg_negated(run_poe_subproc):
    """Inferred option names strip leading underscores for expr arg declarations too"""
    result = run_poe_subproc("private_arg_expr", "--flag", project="expr")
    assert result.stdout == "{'_flag': False, '_FLAG': True}\n"


def test_expr_env_access_uses_typed_and_templated_channels(run_poe_subproc):
    result = run_poe_subproc("bool_env_access_expr", project="expr")
    assert result.stdout == "{'typed': True, 'templated': 'True'}\n"


def test_expr_env_access_unset_bool_arg_preserves_typed_false(run_poe_subproc):
    result = run_poe_subproc("bool_env_access_expr", "--MY_FLAG", project="expr")
    assert result.stdout == "{'typed': False, 'templated': ''}\n"
