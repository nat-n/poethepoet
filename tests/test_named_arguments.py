"""
STILL TO TEST:
- default arguments (declared as a option in the yaml)
- boolean flag arguments, provided or nots
- required args, provided or not
- specifying a the dest option
- automatic documentation of named args
    - when wrong args given
- shell tasks with named arguments
- cmd tasks with named arguments
"""


def test_automatic_kwargs(run_poe_subproc, named_args_project_path):
    result = run_poe_subproc("greet", cwd=named_args_project_path)
    assert result.capture == "Poe => greet\n"
    assert result.stdout == "I'm sorry Dave\n"
    assert result.stderr == ""


def test_script_task_with_args(run_poe_subproc, named_args_project_path):
    result = run_poe_subproc(
        "greet-passed-args",
        "--greeting=hello",
        "--user=nat",
        cwd=named_args_project_path,
    )
    assert result.capture == f"Poe => greet-passed-args --greeting=hello --user=nat\n"
    assert result.stdout == "hello nat default_value None\n"
    assert result.stderr == ""


def test_script_task_with_args_optional(run_poe_subproc, named_args_project_path):
    result = run_poe_subproc(
        "greet-passed-args",
        "--greeting=hello",
        "--user=nat",
        f"--optional=welcome to {named_args_project_path}",
        cwd=named_args_project_path,
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


def test_script_task_default_arg(run_poe_subproc, named_args_project_path):
    result = run_poe_subproc("greet-full-args", cwd=named_args_project_path)
    assert result.capture == f"Poe => greet-full-args\n"
    # hi is the default value for --greeting
    assert result.stdout == f"hi None None None\n"
    assert result.stderr == ""


def test_script_task_include_boolean_flag_and_numeric_args(
    run_poe_subproc, named_args_project_path
):
    result = run_poe_subproc(
        "greet-full-args",
        "--greeting=hello",
        "--user=nat",
        "--upper",
        "--age=42",
        "--height=1.23",
        cwd=named_args_project_path,
    )
    assert result.capture == (
        "Poe => greet-full-args --greeting=hello --user=nat --upper --age=42 "
        "--height=1.23\n"
    )
    assert result.stdout == f"HELLO NAT 1.23 42\n"
    assert result.stderr == ""


def test_script_task_bad_type(run_poe_subproc, poe_project_path):
    project_path = poe_project_path.joinpath("tests", "fixtures", "malformed_project")
    result = run_poe_subproc("bad-type", "--greeting=hello", cwd=project_path)
    assert (
        "Error: 'datetime' is not a valid type for arg 'greeting' of task 'bad-type'. "
        "Choose one of {boolean float integer string} \n" in result.capture
    )
    assert result.stdout == ""
    assert result.stderr == ""
