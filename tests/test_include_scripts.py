import shutil

import pytest


def test_docs_with_included_tasks(run_poe, projects):
    result = run_poe(project="include_scripts")
    assert (
        "Configured tasks:\n"
        "  check-vars             \n"
        "  check-args             Checking that we can pass an arg\n"
        "    --something          This is the arg\n"
        "  script-executor        \n"
        "  cwd                    \n"
        "  confdir                \n"
        "  check-vars-again       \n"
        "  check-args-again       Checking that we can pass an arg\n"
        "    --something          This is the arg\n"
        "  script-executor-again  \n"
        "  cwd-again              \n"
        "  confdir-again          \n"
        "  package-task           \n"
    ) in result.capture
    assert result.stdout == ""


@pytest.mark.skipif(not shutil.which("uv"), reason="No uv available")
def test_config_level_env_and_envfile(run_poe, projects):
    result = run_poe("check-vars", project="include_scripts")
    assert (
        "Poe => poe_test_echo 'ENV_VAR:ENV_VAL\nENVFILE_VAR:ENVFILE_VAL'"
        in result.capture
    )
    assert result.stdout == "ENV_VAR:ENV_VAL\nENVFILE_VAR:ENVFILE_VAL\n"


@pytest.mark.skipif(not shutil.which("uv"), reason="No uv available")
def test_task_with_and_without_executor(run_poe, projects):
    result = run_poe("script-executor", project="include_scripts")
    assert "Poe => poe_test_echo build_time:uv" in result.capture
    assert result.stdout.startswith("build_time:uv, run_time:uv")

    result = run_poe("script-executor-again", project="include_scripts")
    assert "Poe => poe_test_echo build_time:simple" in result.capture
    assert result.stdout.startswith("build_time:simple, run_time:uv")


@pytest.mark.skipif(not shutil.which("uv"), reason="No uv available")
def test_included_script_with_cwd(run_poe, projects, is_windows):
    # check the cwd gets set properly for the task when cwd option set on include
    result = run_poe("cwd", project="include_scripts")
    assert "Poe => poe_test_pwd" in result.capture
    assert result.stdout.endswith("include_scripts_project\n")

    result = run_poe("cwd-more", project="include_scripts")
    assert "Poe => poe_test_pwd" in result.capture
    if is_windows:
        assert result.stdout.endswith("include_scripts_project\\src\n")
    else:
        assert result.stdout.endswith("include_scripts_project/src\n")

    # check POE_CONF_DIR gets set properly for the task when cwd option set on include
    result = run_poe("confdir", project="include_scripts")
    if is_windows:
        assert "Poe => poe_test_echo 'POE_CONF_DIR=" in result.capture
    else:
        assert "Poe => poe_test_echo POE_CONF_DIR=" in result.capture
    assert result.stdout.startswith("POE_CONF_DIR=")
    assert result.stdout.endswith("include_scripts_project\n")

    result = run_poe("confdir-more", project="include_scripts")
    if is_windows:
        assert "Poe => poe_test_echo 'POE_CONF_DIR=" in result.capture
        assert result.stdout.endswith("include_scripts_project\\src\n")
    else:
        assert "Poe => poe_test_echo POE_CONF_DIR=" in result.capture
        assert result.stdout.endswith("include_scripts_project/src\n")


INCLUDE_SCRIPT_ERRORS_MODULE = """
def as_list():
    return [1, 2]

def as_none():
    return None

def as_int():
    return 5

def tool_not_dict():
    return {"tool": "x"}

def tool_poe_not_dict():
    return {"tool": {"poe": "x"}}
"""


@pytest.mark.parametrize(
    ("function_name", "expected_error"),
    [
        ("as_list", "got 'list'"),
        ("as_none", "got 'NoneType'"),
        ("as_int", "got 'int'"),
        ("tool_not_dict", "Unrecognized option 'tool'"),
        ("tool_poe_not_dict", "Option 'tool.poe' must be a table"),
    ],
)
def test_include_script_returning_invalid_config(
    run_poe, temp_pyproject, function_name, expected_error
):
    project_path = temp_pyproject(
        f"""
        [tool.poe]
        executor = "simple"
        include_script = {{ script = "errscripts:{function_name}" }}
        [tool.poe.tasks]
        a = "poe_test_echo a"
        """
    )
    project_path.joinpath("errscripts.py").write_text(INCLUDE_SCRIPT_ERRORS_MODULE)
    result = run_poe("a", cwd=project_path)
    assert result.code == 1
    assert "Error: Invalid content in loaded config from errscripts" in result.capture
    assert expected_error in result.capture


@pytest.mark.parametrize("include_script", ["5", "[5]", '["tasks:x", true]'])
def test_include_script_item_of_invalid_type(run_poe, temp_pyproject, include_script):
    project_path = temp_pyproject(
        f"""
        [tool.poe]
        include_script = {include_script}
        [tool.poe.tasks]
        a = "poe_test_echo a"
        """
    )
    result = run_poe("a", cwd=project_path)
    assert result.code == 1
    assert "Error: Option 'include_script" in result.capture
    assert "must have a value of type" in result.capture
