"""
STILL TO TEST:
- specifying a value for the dest in the args of the task def
- automatic documentation of named args
- specifying alternate options (e.g. --help, -h)
"""


def test_script_task_with_hard_coded_args(run_poe_subproc, projects, esc_prefix):
    # The $ has to be escaped or it'll be evaluated by the outer shell and poe will
    # never see it
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


def test_script_task_with_cli_args(run_poe_subproc):
    result = run_poe_subproc(
        "greet-passed-args", "--greeting=hello", "--user=nat", project="scripts",
    )
    assert result.capture == f"Poe => greet-passed-args --greeting=hello --user=nat\n"
    assert result.stdout == "hello nat 👋 None\n"
    assert result.stderr == ""


def test_script_task_with_args_optional(run_poe_subproc, projects):
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


def test_wrong_args_passed(run_poe_subproc):
    base_error = (
        "usage: poe greet-full-args [--greeting GREETING] [--user USER] [--upper]\n"
        "                           [--age AGE] [--height HEIGHT]\n"
        "poe greet-full-args: error:"
    )

    result = run_poe_subproc("greet-full-args", "--age=lol", project="scripts")
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (f"{base_error} argument --age: invalid int value: 'lol'\n")

    result = run_poe_subproc("greet-full-args", "--age", project="scripts")
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (f"{base_error} argument --age: expected one argument\n")

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


def test_script_task_bad_type(run_poe_subproc, poe_project_path):
    project_path = poe_project_path.joinpath("tests", "fixtures", "malformed_project")
    result = run_poe_subproc("bad-type", "--greeting=hello", cwd=project_path)
    assert (
        "Error: 'datetime' is not a valid type for arg 'greeting' of task 'bad-type'. "
        "Choose one of {boolean float integer string} \n" in result.capture
    )
    assert result.stdout == ""
    assert result.stderr == ""
