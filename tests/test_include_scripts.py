import shutil

import pytest


def test_docs_with_included_tasks(run_poe_subproc, projects):
    result = run_poe_subproc(project="include_scripts")
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
def test_config_level_env_and_envfile(run_poe_subproc, projects):
    result = run_poe_subproc("check-vars", project="include_scripts")
    assert (
        "Poe => poe_test_echo 'ENV_VAR:ENV_VAL\nENVFILE_VAR:ENVFILE_VAL'"
        in result.capture
    )
    assert result.stdout == "ENV_VAR:ENV_VAL\nENVFILE_VAR:ENVFILE_VAL\n"


@pytest.mark.skipif(not shutil.which("uv"), reason="No uv available")
def test_task_with_and_without_executor(run_poe_subproc, projects):
    result = run_poe_subproc("script-executor", project="include_scripts")
    assert "Poe => poe_test_echo build_time:uv" in result.capture
    assert result.stdout.startswith("build_time:uv, run_time:uv")

    result = run_poe_subproc("script-executor-again", project="include_scripts")
    assert "Poe => poe_test_echo build_time:simple" in result.capture
    assert result.stdout.startswith("build_time:simple, run_time:uv")


@pytest.mark.skipif(not shutil.which("uv"), reason="No uv available")
def test_included_script_with_cwd(run_poe_subproc, projects, is_windows):
    # check the cwd gets set properly for the task when cwd option set on include
    result = run_poe_subproc("cwd", project="include_scripts")
    assert "Poe => poe_test_pwd" in result.capture
    assert result.stdout.endswith("include_scripts_project\n")

    result = run_poe_subproc("cwd-more", project="include_scripts")
    assert "Poe => poe_test_pwd" in result.capture
    if is_windows:
        assert result.stdout.endswith("include_scripts_project\\src\n")
    else:
        assert result.stdout.endswith("include_scripts_project/src\n")

    # check POE_CONF_DIR gets set properly for the task when cwd option set on include
    result = run_poe_subproc("confdir", project="include_scripts")
    if is_windows:
        assert "Poe => poe_test_echo 'POE_CONF_DIR=" in result.capture
    else:
        assert "Poe => poe_test_echo POE_CONF_DIR=" in result.capture
    assert result.stdout.startswith("POE_CONF_DIR=")
    assert result.stdout.endswith("include_scripts_project\n")

    result = run_poe_subproc("confdir-more", project="include_scripts")
    if is_windows:
        assert "Poe => poe_test_echo 'POE_CONF_DIR=" in result.capture
        assert result.stdout.endswith("include_scripts_project\\src\n")
    else:
        assert "Poe => poe_test_echo POE_CONF_DIR=" in result.capture
        assert result.stdout.endswith("include_scripts_project/src\n")
