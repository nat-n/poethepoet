import os
import tempfile
import toml


def test_setting_run_in_project_root_option(
    run_poe_subproc, dummy_project_path, poe_project_path
):
    # Set the cwd to something random
    os.chdir(tempfile.gettempdir())
    somewhere_else = os.getcwd()

    # The $ has to be escaped or it'll be evaluated by the outer shell and poe will
    # never see it
    with dummy_project_path.joinpath("pyproject.toml").open("r") as pyproject_file:
        config = toml.load(pyproject_file)["tool"]["poe"]

    # Validate default is to run in the directory with the pyproject.toml
    result = run_poe_subproc(
        "--root", dummy_project_path, "pwd", cwd=poe_project_path, config=config
    )
    assert result.capture == f"Poe => pwd\n"
    assert result.stdout == f"{dummy_project_path}\n"

    # Disable default behavoir of running in project root
    config["run_in_project_root"] = False
    result = run_poe_subproc(
        "--root", dummy_project_path, "pwd", cwd=poe_project_path, config=config
    )
    assert result.capture == f"Poe => pwd\n"
    assert result.stdout == f"{somewhere_else}\n"


def test_setting_default_task_type(run_poe_subproc, scripts_project_path):
    result = run_poe_subproc(
        "greet", "nat,", r"welcome to \${POE_ROOT}", cwd=scripts_project_path
    )
    assert result.capture == f"Poe => greet nat, welcome to {scripts_project_path}\n"
    assert result.stdout == f"hello nat, welcome to {scripts_project_path}\n"
    assert result.stderr == ""
