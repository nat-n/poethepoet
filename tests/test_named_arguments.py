"""
STILL TO TEST:
- specifying a the dest option
- automatic documentation of named args
- specifying alternate options (e.g. --help, -h)
- shell tasks with named arguments
- cmd tasks with named arguments
"""


def test_automatic_kwargs(run_poe_subproc):
    result = run_poe_subproc("greet", project="named_args")
    assert result.capture == "Poe => greet\n"
    assert result.stdout == "I'm sorry Dave\n"
    assert result.stderr == ""


def test_script_task_with_args(run_poe_subproc):
    result = run_poe_subproc(
        "greet-passed-args", "--greeting=hello", "--user=nat", project="named_args",
    )
    assert result.capture == f"Poe => greet-passed-args --greeting=hello --user=nat\n"
    assert result.stdout == "hello nat default_value None\n"
    assert result.stderr == ""


def test_script_task_with_args_optional(run_poe_subproc, projects):
    named_args_project_path = projects["named_args"]
    result = run_poe_subproc(
        "greet-passed-args",
        "--greeting=hello",
        "--user=nat",
        f"--optional=welcome to {named_args_project_path}",
        project="named_args",
    )
    assert result.capture == (
        f"Poe => greet-passed-args --greeting=hello --user=nat --optional=welcome "
        f"to {named_args_project_path}\n"
    )
    assert (
        result.stdout
        == f"hello nat default_value welcome to {named_args_project_path}\n"
    )
    assert result.stderr == ""


def test_script_task_default_arg(run_poe_subproc):
    result = run_poe_subproc("greet-full-args", project="named_args")
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
        project="named_args",
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

    result = run_poe_subproc("greet-full-args", "--age=lol", project="named_args")
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (f"{base_error} argument --age: invalid int value: 'lol'\n")

    result = run_poe_subproc("greet-full-args", "--age", project="named_args")
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (f"{base_error} argument --age: expected one argument\n")

    result = run_poe_subproc("greet-full-args", "--age 3 2 1", project="named_args")
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (f"{base_error} unrecognized arguments: --age 3 2 1\n")

    result = run_poe_subproc("greet-full-args", "--potatoe", project="named_args")
    assert result.capture == ""
    assert result.stdout == ""
    assert result.stderr == (f"{base_error} unrecognized arguments: --potatoe\n")


def test_required_args(run_poe_subproc):
    result = run_poe_subproc(
        "greet-strict", "--greeting=yo", "--name", "dude", project="named_args"
    )
    assert result.capture == "Poe => greet-strict --greeting=yo --name dude\n"
    assert result.stdout == "yo dude\n"
    assert result.stderr == ""

    result = run_poe_subproc("greet-strict", project="named_args")
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
