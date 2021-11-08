import difflib


def test_script_task_with_hard_coded_args(run_poe_subproc, projects, esc_prefix):
    result = run_poe_subproc("static-args-test", project="scripts")
    assert result.capture == f"Poe => static-args-test\n"
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


def test_call_attr_func(run_poe_subproc):
    result = run_poe_subproc("call_attrs", project="scripts")
    assert result.capture == "Poe => call_attrs\n"
    assert result.stdout == "task!\n"
    assert result.stderr == ""


def test_automatic_kwargs_from_args(run_poe_subproc):
    result = run_poe_subproc("greet", project="scripts")
    assert result.capture == "Poe => greet\n"
    assert result.stdout == "I'm sorry Dave\n"
    assert result.stderr == ""


def test_script_task_with_cli_args(run_poe_subproc, is_windows):

    result = run_poe_subproc(
        "greet-passed-args",
        "--greeting=hello",
        "--user=nat",
        project="scripts",
    )
    assert (
        result.capture == f"Poe => greet-passed-args --greeting=hello --user=nat\n"
    ), [
        li
        for li in difflib.ndiff(
            result.capture, f"Poe => greet-passed-args --greeting=hello --user=nat\n"
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
    )
    assert result.capture == (
        f"Poe => greet-passed-args --greeting=hello --user=nat --optional=welcome "
        f"to {named_args_project_path}\n"
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
    result = run_poe_subproc("greet-full-args", project="scripts")
    assert result.capture == f"Poe => greet-full-args\n"
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

    result = run_poe_subproc("greet-full-args", "--age=lol", project="scripts")
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (
        f"{base_error} argument --age/-a: invalid int value: 'lol'\n"
    )

    result = run_poe_subproc("greet-full-args", "--age", project="scripts")
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (f"{base_error} argument --age/-a: expected one argument\n")

    result = run_poe_subproc("greet-full-args", "--age 3 2 1", project="scripts")
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (f"{base_error} unrecognized arguments: --age 3 2 1\n")

    result = run_poe_subproc("greet-full-args", "--potatoe", project="scripts")
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (f"{base_error} unrecognized arguments: --potatoe\n")


def test_required_args(run_poe_subproc):
    result = run_poe_subproc(
        "greet-strict", "--greeting=yo", "--name", "dude", project="scripts"
    )
    assert result.capture == "Poe => greet-strict --greeting=yo --name dude\n"
    assert result.stdout == "yo dude\n"
    assert result.stderr == ""

    result = run_poe_subproc("greet-strict", project="scripts")
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (
        "usage: poe greet-strict --greeting GREETING --name NAME\npoe greet-strict: "
        "error: the following arguments are required: --greeting, --name\n"
    )


def test_script_task_bad_type(run_poe_subproc, projects):
    result = run_poe_subproc(
        f'--root={projects["scripts/bad_type"]}',
        "bad-type",
        "--greeting=hello",
    )
    assert (
        "Error: 'datetime' is not a valid type for arg 'greeting' of task 'bad-type'. "
        "Choose one of {boolean float integer string} \n" in result.capture
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_script_with_positional_args(run_poe_subproc):
    result = run_poe_subproc("greet-positional", "help!", "Santa", project="scripts")
    assert result.capture == "Poe => greet-positional help! Santa\n"
    assert result.stdout == "help! Santa\n"
    assert result.stderr == ""

    # Ommission of optional positional arg
    result = run_poe_subproc("greet-positional", "Santa", project="scripts")
    assert result.capture == "Poe => greet-positional Santa\n"
    assert result.stdout == "yo Santa\n"
    assert result.stderr == ""

    # Ommission of required positional arg
    result = run_poe_subproc("greet-positional", project="scripts")
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (
        "usage: poe greet-positional [--upper] [greeting] user\n"
        "poe greet-positional: error: the following arguments are required: user\n"
    )

    # Too many positional args
    result = run_poe_subproc(
        "greet-positional", "plop", "plop", "plop", project="scripts"
    )
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (
        "usage: poe greet-positional [--upper] [greeting] user\n"
        "poe greet-positional: error: unrecognized arguments: plop\n"
    )


def test_script_with_positional_args_and_options(run_poe_subproc):
    result = run_poe_subproc(
        "greet-positional", "help!", "Santa", "--upper", project="scripts"
    )
    assert result.capture == "Poe => greet-positional help! Santa --upper\n"
    assert result.stdout == "HELP! SANTA\n"
    assert result.stderr == ""

    result = run_poe_subproc(
        "greet-positional", "--upper", "help!", "Santa", project="scripts"
    )
    assert result.capture == "Poe => greet-positional --upper help! Santa\n"
    assert result.stdout == "HELP! SANTA\n"
    assert result.stderr == ""
