import difflib

no_venv = {"POETRY_VIRTUALENVS_CREATE": "false"}


def test_script_task_with_hard_coded_args(run_poe_subproc, projects, esc_prefix):
    result = run_poe_subproc("static-args-test", project="scripts", env=no_venv)
    assert result.capture == "Poe => static-args-test\n"
    assert result.stdout == (
        "str: pat a cake\n"
        "int: 1\n"
        "float: 1.2\n"
        "bool: False\n"
        "bool: True\n"
        "ellipsis: Ellipsis\n"
        "str: 0x63\n"
        "str: 7\n"
        "tuple: ('first', ('second', 'lol'))\n"
        "bool: True\n"
        "spread => set: {1, 2, 3}\n"
        "thing => str: stuff\n"
        "data1 => bytes: b'stuff'\n"
        "data2 => bytes: b'BCD'\n"
        "eight => tuple: (8, 8.0, 8)\n"
    )
    assert result.stderr == ""


def test_call_attr_func_with_exec(run_poe_subproc):
    result = run_poe_subproc("call_attrs", project="scripts", env=no_venv)
    assert result.capture == "Poe => call_attrs\n"
    assert result.stdout == "task!\n"
    assert result.stderr == ""


def test_print_result(run_poe_subproc):
    result = run_poe_subproc("print-script-result", project="scripts", env=no_venv)
    assert result.capture == "Poe => print-script-result\n"
    assert result.stdout == "determining most random number...\n7\n"
    assert result.stderr == ""


def test_dont_print_result(run_poe_subproc):
    result = run_poe_subproc("dont-print-script-result", project="scripts", env=no_venv)
    assert result.capture == "Poe => dont-print-script-result\n"
    assert result.stdout == "determining most random number...\n"
    assert result.stderr == ""


def test_automatic_kwargs_from_args(run_poe_subproc):
    result = run_poe_subproc("greet", project="scripts", env=no_venv)
    assert result.capture == "Poe => greet\n"
    assert result.stdout == "I'm sorry Dave\n"
    assert result.stderr == ""


def test_script_task_with_cli_args(run_poe_subproc, is_windows):
    result = run_poe_subproc(
        "greet-passed-args",
        "--greeting=hello",
        "--user=nat",
        project="scripts",
        env=no_venv,
    )
    assert result.capture == "Poe => greet-passed-args --greeting=hello --user=nat\n", [
        li
        for li in difflib.ndiff(
            result.capture, "Poe => greet-passed-args --greeting=hello --user=nat\n"
        )
        if li[0] != " "
    ]
    if is_windows:
        assert result.stdout == "hello nat \\U0001f44b None\n"
    else:
        assert result.stdout == "hello nat 👋 None\n"
    assert result.stderr == ""


def test_script_task_with_args_optional(run_poe_subproc, projects, is_windows):
    named_args_project_path = projects["scripts"]
    result = run_poe_subproc(
        "greet-passed-args",
        "--greeting=hello",
        "--user=nat",
        f"--optional=welcome to {named_args_project_path}",
        project="scripts",
        env=no_venv,
    )
    assert result.capture == (
        f"Poe => greet-passed-args --greeting=hello --user=nat "
        f"'--optional=welcome to {named_args_project_path}'\n"
    )

    if is_windows:
        assert (
            result.stdout
            == f"hello nat \\U0001f44b welcome to {named_args_project_path}\n"
        )
    else:
        assert result.stdout == f"hello nat 👋 welcome to {named_args_project_path}\n"

    assert result.stderr == ""


def test_script_task_default_arg(run_poe_subproc):
    result = run_poe_subproc("greet-full-args", project="scripts", env=no_venv)
    assert result.capture == "Poe => greet-full-args\n"
    # hi is the default value for --greeting
    assert result.stdout == "hi None None None\n"
    assert result.stderr == ""


def test_script_task_include_boolean_flag_and_numeric_args(run_poe_subproc):
    result = run_poe_subproc(
        "greet-full-args",
        "--greeting=hello",
        "--user=nat",
        "--upper",
        "--age=42",
        "--height=1.23",
        project="scripts",
        env=no_venv,
    )
    assert result.capture == (
        "Poe => greet-full-args --greeting=hello --user=nat --upper --age=42 "
        "--height=1.23\n"
    )
    assert result.stdout == "HELLO NAT 1.23 42\n"
    assert result.stderr == ""


def test_script_task_with_short_args(run_poe_subproc):
    result = run_poe_subproc(
        "greet-full-args",
        "-g=Ciao",
        "--user=toni",
        "-a",
        "109",
        "-h=1.09",
        project="scripts",
        env=no_venv,
    )
    assert result.capture == (
        "Poe => greet-full-args -g=Ciao --user=toni -a 109 -h=1.09\n"
    )
    assert result.stdout == "Ciao toni 1.09 109\n"
    assert result.stderr == ""


def test_wrong_args_passed(run_poe_subproc):
    base_error = (
        "usage: poe greet-full-args [--greeting GREETING] [--user USER] [--upper]\n"
        "                           [--age AGE] [--height USER_HEIGHT]\n"
        "poe greet-full-args: error:"
    )

    result = run_poe_subproc(
        "greet-full-args", "--age=lol", project="scripts", env=no_venv
    )
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (
        f"{base_error} argument --age/-a: invalid int value: 'lol'\n"
    )

    result = run_poe_subproc("greet-full-args", "--age", project="scripts", env=no_venv)
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (f"{base_error} argument --age/-a: expected one argument\n")

    result = run_poe_subproc(
        "greet-full-args", "--age 3 2 1", project="scripts", env=no_venv
    )
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (f"{base_error} unrecognized arguments: --age 3 2 1\n")

    result = run_poe_subproc(
        "greet-full-args", "--potato", project="scripts", env=no_venv
    )
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (f"{base_error} unrecognized arguments: --potato\n")


def test_required_args(run_poe_subproc):
    result = run_poe_subproc(
        "greet-strict",
        "--greeting=yo",
        "--name",
        "dude",
        project="scripts",
        env=no_venv,
    )
    assert result.capture == "Poe => greet-strict --greeting=yo --name dude\n"
    assert result.stdout == "yo dude\n"
    assert result.stderr == ""

    result = run_poe_subproc("greet-strict", project="scripts", env=no_venv)
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (
        "usage: poe greet-strict --greeting GREETING --name NAME\npoe greet-strict: "
        "error: the following arguments are required: --greeting, --name\n"
    )


def test_script_task_bad_type(run_poe_subproc, projects):
    result = run_poe_subproc(
        f'-C={projects["scripts/bad_type"]}',
        "bad-type",
        "--greeting=hello",
    )
    assert (
        "Error: Invalid argument 'greeting' declared in task 'bad-type'\n"
        "     | Option 'type' must be one of "
        "('string', 'float', 'integer', 'boolean')\n"
    ) in result.capture

    assert result.stdout == ""
    assert result.stderr == ""


def test_script_task_bad_content(run_poe_subproc, projects):
    result = run_poe_subproc(
        f'-C={projects["scripts/bad_content"]}',
        "bad-content",
        "--greeting=hello",
    )
    assert (
        "Error: Invalid task 'bad-type'\n"
        "     | Invalid callable reference 'dummy_package:main[greeting]'\n"
        "     | (expected something like `module:callable` or `module:callable()`)\n"
    ) in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_script_with_positional_args(run_poe_subproc):
    result = run_poe_subproc(
        "greet-positional", "help!", "Santa", project="scripts", env=no_venv
    )
    assert result.capture == "Poe => greet-positional 'help!' Santa\n"
    assert result.stdout == "help! Santa\n"
    assert result.stderr == ""

    # Omission of optional positional arg
    result = run_poe_subproc(
        "greet-positional", "Santa", project="scripts", env=no_venv
    )
    assert result.capture == "Poe => greet-positional Santa\n"
    assert result.stdout == "yo Santa\n"
    assert result.stderr == ""

    # Omission of required positional arg
    result = run_poe_subproc("greet-positional", project="scripts", env=no_venv)
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (
        "usage: poe greet-positional [--upper] [greeting] user\n"
        "poe greet-positional: error: the following arguments are required: user\n"
    )

    # Too many positional args
    result = run_poe_subproc(
        "greet-positional", "plop", "plop", "plop", project="scripts", env=no_venv
    )
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (
        "usage: poe greet-positional [--upper] [greeting] user\n"
        "poe greet-positional: error: unrecognized arguments: plop\n"
    )


def test_script_with_positional_args_and_options(run_poe_subproc):
    result = run_poe_subproc(
        "greet-positional", "help!", "Santa", "--upper", project="scripts", env=no_venv
    )
    assert result.capture == "Poe => greet-positional 'help!' Santa --upper\n"
    assert result.stdout == "HELP! SANTA\n"
    assert result.stderr == ""

    result = run_poe_subproc(
        "greet-positional", "--upper", "help!", "Santa", project="scripts", env=no_venv
    )
    assert result.capture == "Poe => greet-positional --upper 'help!' Santa\n"
    assert result.stdout == "HELP! SANTA\n"
    assert result.stderr == ""


def test_script_with_multi_value_args(run_poe_subproc):
    # Test with all args
    result = run_poe_subproc(
        "multiple-value-args",
        "hey",
        "1",
        "2",
        "3",
        "--widgets",
        "cow",
        "dog",
        "--engines",
        "v2",
        "v8",
        project="scripts",
        env=no_venv,
    )
    assert (
        result.capture
        == "Poe => multiple-value-args hey 1 2 3 --widgets cow dog --engines v2 v8\n"
    )
    assert result.stdout == (
        "args ('hey', [1, 2, 3])\n"
        "kwargs {'widgets': ['cow', 'dog'], 'engines': ['v2', 'v8']}\n"
    )
    assert result.stderr == ""

    # Test with some args
    result = run_poe_subproc(
        "multiple-value-args", "1", "--engines", "v2", project="scripts", env=no_venv
    )
    assert result.capture == "Poe => multiple-value-args 1 --engines v2\n"
    assert result.stdout == (
        "args ('1', [])\nkwargs {'widgets': None, 'engines': ['v2']}\n"
    )
    assert result.stderr == ""

    # Test with minimal args
    result = run_poe_subproc(
        "multiple-value-args", "--engines", "v2", project="scripts", env=no_venv
    )
    assert result.capture == "Poe => multiple-value-args --engines v2\n"
    assert result.stdout == (
        "args (None, [])\nkwargs {'widgets': None, 'engines': ['v2']}\n"
    )
    assert result.stderr == ""

    # Not enough values for option: 0
    result = run_poe_subproc(
        "multiple-value-args",
        "--engines",
        "v2",
        "--widgets",
        project="scripts",
        env=no_venv,
    )
    assert result.capture == ""
    assert result.stdout == ""
    assert (
        "poe multiple-value-args: error: argument --widgets: expected 2 arguments"
        in result.stderr
    )

    # Too many values for option: 3
    result = run_poe_subproc(
        "multiple-value-args",
        "bloop",  # without the first arg, dong gets read an positional
        "--engines",
        "v2",
        "--widgets",
        "ding",
        "dang",
        "dong",
        project="scripts",
        env=no_venv,
    )
    assert result.capture == ""
    assert result.stdout == ""
    # accomodate difference in argparse output between python versions
    assert (
        "poe multiple-value-args: error: argument second: invalid int value: 'dong'"
        in result.stderr
    ) or (
        "poe multiple-value-args: error: unrecognized arguments: dong" in result.stderr
    )

    # wrong type for multiple values
    result = run_poe_subproc(
        "multiple-value-args",
        "1",
        "wrong",
        "--engines",
        "v2",
        project="scripts",
        env=no_venv,
    )
    assert result.capture == ""
    assert result.stdout == ""
    assert (
        "poe multiple-value-args: error: argument second: invalid int value: 'wrong'"
        in result.stderr
    )


def test_async_script_task(run_poe_subproc, projects):
    result = run_poe_subproc(
        "async-task",
        "--a=foo",
        "--b=bar",
        project="scripts",
        env=no_venv,
    )
    assert result.capture == "Poe => async-task --a=foo --b=bar\n"
    assert result.stdout == "I'm an async task! () {'a': 'foo', 'b': 'bar'}\n"
    assert result.stderr == ""
