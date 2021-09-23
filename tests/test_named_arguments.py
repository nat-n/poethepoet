"""
STILL TO TEST:
- default arguments (declared as a option in the yaml)
- boolean flag arguments, provided or nots
- required args, provided or not
- specifying a the dest option
"""


def test_automatic_kwargs(run_poe_subproc, named_args_project_path):
    result = run_poe_subproc("greet", cwd=named_args_project_path)
    assert result.capture == "Poe => greet\n"
    assert result.stdout == "I'm sorry Dave\n"
    assert result.stderr == ""


def test_script_task_with_args(run_poe_subproc, named_args_project_path):
    result = run_poe_subproc(
        "greet-keyed", "--greeting=hello", "--user=nat", cwd=named_args_project_path
    )
    assert result.capture == f"Poe => greet-keyed --greeting=hello --user=nat\n"
    assert result.stdout == "hello nat default_value None\n"
    assert result.stderr == ""


def test_script_task_with_args_optional(run_poe_subproc, named_args_project_path):
    result = run_poe_subproc(
        "greet-keyed",
        "--greeting=hello",
        "--user=nat",
        f"--optional=welcome to {named_args_project_path}",
        cwd=named_args_project_path,
    )
    assert (
        result.capture
        == f"Poe => greet-keyed --greeting=hello --user=nat --optional=welcome to {named_args_project_path}\n"
    )
    assert (
        result.stdout
        == f"hello nat default_value welcome to {named_args_project_path}\n"
    )
    assert result.stderr == ""


def test_script_task_omit_kwarg(run_poe_subproc, named_args_project_path):
    result = run_poe_subproc(
        "greet-keyed",
        "--greeting=hello",
        f"--optional=welcome to {named_args_project_path}",
        cwd=named_args_project_path,
    )
    assert (
        result.capture
        == f"Poe => greet-keyed --greeting=hello --optional=welcome to {named_args_project_path}\n"
    )
    assert (
        result.stdout
        == f"hello user default_value welcome to {named_args_project_path}\n"
    )
    assert result.stderr == ""


def test_script_task_renamed(run_poe_subproc, named_args_project_path):
    result = run_poe_subproc(
        "greet-rekeyed",
        "--greeting=hello",
        "--user=nat",
        f"--opt=welcome to {named_args_project_path}",
        cwd=named_args_project_path,
    )
    assert (
        result.capture
        == f"Poe => greet-rekeyed --greeting=hello --user=nat --opt=welcome to {named_args_project_path}\n"
    )
    assert result.stdout == f"hello nat default welcome to {named_args_project_path}\n"
    assert result.stderr == ""


def test_script_task_renamed_upper(run_poe_subproc, named_args_project_path):
    result = run_poe_subproc(
        "greet-rekeyed",
        "--greeting=hello",
        "--user=nat",
        f"--opt=welcome to {named_args_project_path}",
        "--upper=Any-Value",
        cwd=named_args_project_path,
    )
    assert (
        result.capture
        == f"Poe => greet-rekeyed --greeting=hello --user=nat --opt=welcome to {named_args_project_path} --upper=Any-Value\n"
    )
    assert result.stdout == f"HELLO NAT DEFAULT welcome to {named_args_project_path}\n"
    assert result.stderr == ""


def test_script_task_bad_type(run_poe_subproc, poe_project_path):
    project_path = poe_project_path.joinpath("tests", "fixtures", "malformed_project")
    result = run_poe_subproc("bad-type", "--greeting=hello", cwd=project_path)
    assert (
        "Error: 'datetime' is not a valid type for -> arg 'greeting' of task 'bad-type'.Choose one of ['float', 'integer', 'string']"
        in result.capture
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_script_task_renamed_omit(run_poe_subproc, named_args_project_path):
    result = run_poe_subproc(
        "greet-rekeyed", "--greeting=hello", "--fvar=0.001", cwd=named_args_project_path
    )
    assert result.capture == f"Poe => greet-rekeyed --greeting=hello --fvar=0.001\n"
    assert result.stdout == f"hello user default 0.001 None\n"
    assert result.stderr == ""
