import pytest


def test_customize_program_name(run_poe, projects):
    result = run_poe(program_name="boop")
    assert "Usage:\n  boop [global options] task" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_bad_args_doc_with_custom_program_name(run_poe, projects):
    result = run_poe("async-task", "--fail", program_name="boop", project="scripts")
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.capture == (
        "usage: boop async-task [--a A] [--b B]\n"
        "boop async-task: error: unrecognized arguments: --fail\n"
        "Error: Invalid arguments for task 'async-task'\n"
    )


def test_customize_config_name(run_poe, projects):
    result = run_poe("hello", config_name="tasks.toml", project="custom_config")
    assert result.capture == "Poe => poe_test_echo hello from tasks.toml\n"
    assert result.stdout == "hello from tasks.toml\n"
    assert result.stderr == ""


def test_customize_config_name_with_json(run_poe, projects):
    result = run_poe("hello", config_name="tasks.json", project="custom_config")
    assert result.capture == "Poe => poe_test_echo hello from tasks.json\n"
    assert result.stdout == "hello from tasks.json\n"
    assert result.stderr == ""

    result = run_poe(
        "-C",
        str(projects["custom_config"]),
        "hello",
        config_name="tasks.json",
    )
    assert result.capture == "Poe => poe_test_echo hello from tasks.json\n"
    assert result.stdout == "hello from tasks.json\n"
    assert result.stderr == ""


def test_running_tasks_does_not_stop_active_coverage(run_poe, temp_pyproject):
    """
    Running a task in-process must leave a coverage tracer in the caller untouched.
    """
    coverage = pytest.importorskip("coverage")
    project_path = temp_pyproject("""
        [tool.poe]
        executor = "simple"

        [tool.poe.tasks]
        greet = "poe_test_echo hi"
        """)
    cov = coverage.Coverage(data_file=None)
    cov.start()
    try:
        result = run_poe("greet", cwd=project_path)
        coverage_still_active = coverage.Coverage.current() is cov
    finally:
        cov.stop()
    assert result.code == 0
    assert result.stdout == "hi\n"
    assert coverage_still_active, "Running a task stopped the caller's coverage"


@pytest.mark.parametrize(
    "config",
    [
        {"executor": "simple", "tasks": {"hi": "poe_test_echo hi from dict"}},
        {
            "tool": {
                "poe": {
                    "executor": "simple",
                    "tasks": {"hi": "poe_test_echo hi from dict"},
                }
            }
        },
    ],
)
def test_config_from_mapping(run_poe, tmp_path, projects, config):
    # works without any config file present
    result = run_poe("hi", config=config, cwd=tmp_path)
    assert result.code == 0
    assert result.capture == "Poe => poe_test_echo hi from dict\n"
    assert result.stdout == "hi from dict\n"

    # takes precedence over a config file in the cwd
    result = run_poe("hi", config=config, project="example")
    assert result.code == 0
    assert result.stdout == "hi from dict\n"
    result = run_poe("echo", config=config, project="example")
    assert result.code == 1
    assert "Error: Unrecognized task 'echo'" in result.capture


def test_invalid_config_from_mapping(run_poe, tmp_path):
    result = run_poe("hi", config={"tasks": {"hi": 5}, "bogus": 1}, cwd=tmp_path)
    assert result.code == 1
    assert "Error: Unrecognized option 'bogus'" in result.capture
