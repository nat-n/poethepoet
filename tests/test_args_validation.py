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
        (
            '[{ name = "flag", options = ["flag"] }]',
            "Invalid argument 'flag' declared in task 'bad'\n"
            "     | Invalid CLI option provided 'flag', did you mean '--flag'?",
        ),
        (
            '[{ name = "flag", options = ["  "] }]',
            "Invalid argument 'flag' declared in task 'bad'\n"
            "     | Invalid empty value in CLI options list",
        ),
        (
            '["flag", { name = "flag", options = ["-f"] }]',
            "Invalid argument 'flag' declared in task 'bad'\n"
            "     | Duplicate argument name 'flag'",
        ),
        (
            '[{ name = "one", options = ["-x"] }, { name = "two", options = ["-x"] }]',
            "Arguments 'one' and 'two' generate the same CLI option '-x'",
        ),
        (
            '[{ name = "items", positional = true, multiple = true },'
            ' { name = "last", positional = true }]',
            "Invalid argument 'last' declared in task 'bad'\n"
            "     | Only the last positional arg of task may accept multiple values"
            " (not 'items').",
        ),
        (
            '{ flag = { name = "other" } }',
            "Unexpected 'name' option for argument 'flag'",
        ),
        (
            '{ flag = "--flag" }',
            "Invalid configuration for arg 'flag', expected dict",
        ),
        (
            "[5]",
            "Argument 5 has invalid type, a string or dict is expected",
        ),
        (
            '[{ name = "1st" }]',
            "Invalid argument '1st' declared in task 'bad'\n"
            "     | Argument name '1st' is not a valid 'identifier',",
        ),
        (
            '[{ name = "target", positional = "not valid" }]',
            "Invalid argument 'target' declared in task 'bad'\n"
            "     | positional name 'not valid' for arg 'target' is not a valid"
            " 'identifier'",
        ),
        (
            '[{ name = "flag", options = "--flag" }]',
            "Invalid argument 'flag' declared in task 'bad'\n"
            "     | Option 'options' must be a list",
        ),
        (
            '[{ name = "flag", options = 5 }]',
            "Invalid argument 'flag' declared in task 'bad'\n"
            "     | Option 'options' must be a list",
        ),
        (
            "[{ name = 5 }]",
            "Invalid argument 5 declared in task 'bad'\n"
            "     | Option 'name' must have a value of type: str",
        ),
        (
            '[{ name = "flag", choices = [] }]',
            "Invalid argument 'flag' declared in task 'bad'\n"
            "     | Argument 'flag' must declare at least one choice",
        ),
        (
            '[{ name = "flag", positional = "" }]',
            "Invalid argument 'flag' declared in task 'bad'\n"
            "     | positional name '' for arg 'flag' is not a valid 'identifier'",
        ),
        (
            '["_"]',
            "Invalid argument '_' declared in task 'bad'\n"
            "     | Invalid CLI option provided '--', an option must include a "
            "name after the leading dashes",
        ),
        (
            '[{ name = "flag", options = ["-"] }]',
            "Invalid argument 'flag' declared in task 'bad'\n"
            "     | Invalid CLI option provided '-', an option must include a "
            "name after the leading dashes",
        ),
    ],
    ids=(
        "options_empty",
        "option_without_dash",
        "option_blank",
        "duplicate_name",
        "same_cli_option",
        "positional_multiple_not_last",
        "subtable_name_key",
        "subtable_not_dict",
        "list_item_not_string_or_dict",
        "name_not_identifier",
        "positional_alias_not_identifier",
        "options_string",
        "options_integer",
        "name_integer",
        "choices_empty",
        "positional_empty_string",
        "name_only_underscore",
        "option_only_dashes",
    ),
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
