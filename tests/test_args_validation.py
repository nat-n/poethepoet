import pytest


@pytest.fixture
def generate_args_pyproject(temp_pyproject):
    def generator(args_block: str):
        return temp_pyproject(f"""
            [tool.poe.tasks.bad]
            cmd = "poe_test_echo ok"
            args = {args_block}
            """)

    return generator


@pytest.mark.parametrize(
    ("args_block", "expected_error"),
    [
        (
            '[{ name = "flag", options = [] }]',
            "Invalid argument 'flag' declared in task 'bad'\n"
            "     | Option 'options' requires at least 1 item(s), got 0",
        ),
    ],
    ids=("options_empty",),
)
def test_invalid_args_config_is_rejected(
    generate_args_pyproject, run_poe, args_block, expected_error
):
    project_path = generate_args_pyproject(args_block)
    result = run_poe("bad", cwd=project_path)
    assert result.code == 1
    assert expected_error in result.capture
    assert "Traceback" not in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize("positional", ["true", "false"])
def test_required_arg_with_exact_multiple_must_be_given(
    temp_pyproject, run_poe, positional
):
    project_path = temp_pyproject(f"""
        [tool.poe.tasks.pair]
        cmd = "poe_test_echo ${{items}}"
        [[tool.poe.tasks.pair.args]]
        name = "items"
        positional = {positional}
        multiple = 2
        required = true
        """)
    result = run_poe("pair", cwd=project_path)
    assert result.code == 1
    assert "Error: Invalid arguments for task 'pair'" in result.capture
    assert result.stdout == ""

    result = run_poe(
        "pair",
        *(() if positional == "true" else ("--items",)),
        "a",
        "b",
        cwd=project_path,
    )
    assert result.code == 0
    assert result.capture == "Poe => poe_test_echo a b\n"
    assert result.stdout == "a b\n"
