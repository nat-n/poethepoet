import pytest


@pytest.fixture
def private_positional_pyproject(temp_pyproject):
    project_tmpl = """
        [tool.poe.tasks.greet]
        cmd = "poe_test_echo ${_target}!"

        [[tool.poe.tasks.greet.args]]
        name = "_target"
        positional = true
        required = true
        help = "who to greet"
    """
    return temp_pyproject(project_tmpl)


def test_private_positional_arg_strips_underscore_in_help(
    private_positional_pyproject, run_poe
):
    """Help for a private positional arg shows the stripped name."""
    result = run_poe("-h", "greet", cwd=private_positional_pyproject)
    assert "target" in result.capture
    assert "_target" not in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_private_positional_arg_strips_underscore_in_summary(
    private_positional_pyproject, run_poe
):
    """The task summary view also shows the stripped name for private positionals."""
    result = run_poe(cwd=private_positional_pyproject)
    assert "target" in result.capture
    assert "_target" not in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_private_positional_arg_value_remains_private(
    private_positional_pyproject, run_poe
):
    """The arg value drives the private template var, not a public env var."""
    result = run_poe("greet", "world", cwd=private_positional_pyproject)
    assert result.code == 0
    assert result.capture == "Poe => poe_test_echo 'world!'\n"
    assert result.stdout == "world!\n"
    assert result.stderr == ""


def test_private_positional_dest_collision_is_rejected(temp_pyproject, run_poe):
    """Two positional args that strip to the same identifier are rejected."""
    project_path = temp_pyproject("""
            [tool.poe.tasks.bad]
            cmd = "poe_test_echo ok"
            args = [
              { name = "_target", positional = true },
              { name = "target", positional = true },
            ]
        """)
    result = run_poe("bad", "a", "b", cwd=project_path)
    assert result.code == 1
    assert "same positional identifier 'target'" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("args_block", "expected_error"),
    [
        (
            '{ name = "_target", positional = true }, { name = "target" }',
            "Arguments '_target' and 'target' map to the same argument "
            "identifier 'target'",
        ),
        (
            '{ name = "target" }, { name = "_target", positional = true }',
            "Arguments 'target' and '_target' map to the same argument "
            "identifier 'target'",
        ),
        (
            '{ name = "target", positional = "dest" }, { name = "dest" }',
            "Arguments 'target' and 'dest' map to the same argument identifier 'dest'",
        ),
        (
            '{ name = "first", positional = "second" },'
            ' { name = "second", positional = "third" }',
            "Arguments 'first' and 'second' map to the same argument "
            "identifier 'second'",
        ),
        (
            '{ name = "dry-run" }, { name = "dry_run" }',
            "Arguments 'dry-run' and 'dry_run' map to the same argument "
            "identifier 'dry_run'",
        ),
    ],
    ids=(
        "private_positional_then_option",
        "option_then_private_positional",
        "positional_alias_and_option",
        "positional_alias_and_positional_name",
        "dash_and_underscore_names",
    ),
)
def test_positional_dest_and_option_collision_is_rejected(
    temp_pyproject, run_poe, args_block, expected_error
):
    """
    Args that would share an argparse dest or exposed variable are rejected.
    """
    project_path = temp_pyproject(f"""
            [tool.poe.tasks.bad]
            cmd = "poe_test_echo ok"
            args = [{args_block}]
        """)
    result = run_poe("bad", cwd=project_path)
    assert result.code == 1
    assert "Error: Invalid argument" in result.capture
    assert expected_error in result.capture
    assert result.stdout == ""
    assert result.stderr == ""
