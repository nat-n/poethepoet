"""Tests for task grouping feature."""

import pytest

# -- Help output and heading precedence --


def test_groups_in_help_output(run_poe, projects):
    """Test that tasks are grouped correctly in help output."""
    result = run_poe(cwd=projects["groups"])
    assert result.code == 1, "Expected non-zero result when no task specified"

    output = result.capture
    lines = output.split("\n")

    configured_tasks_idx = None
    for i, line in enumerate(lines):
        if "Configured tasks:" in line:
            configured_tasks_idx = i
            break
    assert configured_tasks_idx is not None, "Should have 'Configured tasks:' section"

    tasks_section = "\n".join(lines[configured_tasks_idx:])

    # Ungrouped tasks appear first
    uncategorized_idx = tasks_section.find("uncategorized")
    assert uncategorized_idx > 0

    # Group headings appear (not internal group names)
    auth_idx = tasks_section.find(" Authentication")
    docker_idx = tasks_section.find(" Docker")
    static_typing_idx = tasks_section.find(" Static Typing")
    assert auth_idx > 0
    assert docker_idx > 0
    assert static_typing_idx > 0
    assert "static_typing" not in tasks_section, "Should use heading, not group name"

    # Ungrouped before groups, groups sorted alphabetically
    assert uncategorized_idx < auth_idx
    assert auth_idx < docker_idx < static_typing_idx

    # Tasks appear under their group headings
    assert tasks_section.find("aws_login") > auth_idx
    assert tasks_section.find("docker_start") > docker_idx
    assert tasks_section.find("check") > static_typing_idx

    # Tasks from included config appear under the same group headings
    assert tasks_section.find("docker_logs") > docker_idx
    assert tasks_section.find("lint") > static_typing_idx

    # Project heading takes precedence (not "Docker (Extra)" or "Static Typing (Extra)")
    assert "Docker (Extra)" not in tasks_section
    assert "Static Typing (Extra)" not in tasks_section


# -- Task execution (project and included groups) --


def test_task_execution_from_group(run_poe, projects):
    """Tasks defined in groups can be executed normally."""
    result = run_poe("check", cwd=projects["groups"])
    assert result.code == 0
    assert "Running mypy..." in result.capture


def test_included_group_task_execution(run_poe, projects):
    """Tasks from an included config's group can be executed."""
    result = run_poe("docker_logs", cwd=projects["groups"])
    assert result.code == 0
    assert "Showing logs..." in result.capture


# -- Executor resolution (inheritance, task/CLI override, cross-include precedence) --


def test_group_executor_inherited(run_poe, projects):
    """Task with no executor in a group with executor='simple' should use simple."""
    result = run_poe("group_show_env", cwd=projects["groups"])
    assert result.code == 0
    assert "POE_ACTIVE=simple" in result.stdout


def test_group_executor_inherited_fails_with_bad_config(run_poe, projects):
    """Task inheriting a virtualenv executor with a missing venv should fail."""
    result = run_poe("venv_group_task", cwd=projects["groups"])
    assert result.code == 1
    assert "nonexistent_venv" in result.capture


def test_group_executor_overridden_by_task(run_poe, projects):
    """Task-level executor overrides group-level executor."""
    result = run_poe("venv_group_task_override", cwd=projects["groups"])
    assert result.code == 0
    assert "override_works" in result.stdout


def test_group_executor_precedence_across_includes(run_poe, projects):
    """Project's group executor takes precedence over include's group executor."""
    # extra_tasks.toml redefines simple_group with a broken virtualenv executor,
    # but the project's executor = "simple" should win.
    result = run_poe("included_group_env", cwd=projects["groups"])
    assert result.code == 0
    assert "POE_ACTIVE=simple" in result.stdout


def test_group_executor_overridden_by_cli(run_poe, projects):
    """CLI --executor overrides group-level executor."""
    result = run_poe("--executor", "simple", "venv_group_task", cwd=projects["groups"])
    assert result.code == 0
    assert "should_not_run" in result.capture


def test_grouped_task_args_aligned_with_help_column(run_poe, temp_pyproject):
    """Args of grouped tasks line up with the help column of other tasks."""
    project_path = temp_pyproject(
        """
        [tool.poe.tasks.top]
        cmd = "poe_test_echo top"
        help = "top task"
        args = [{ name = "aaa", help = "arg help" }]
        [tool.poe.groups.grp.tasks.ingroup]
        cmd = "poe_test_echo ingroup"
        help = "group task"
        args = [{ name = "bbbbbbbbbbbbbbbbbbbb", help = "long arg help" }]
        """
    )
    result = run_poe(cwd=project_path)
    assert (
        "Configured tasks:\n"
        "  top                         top task\n"
        "    --aaa                     arg help\n"
        "\n"
        " grp\n"
        "  ingroup                     group task\n"
        "      --bbbbbbbbbbbbbbbbbbbb  long arg help\n"
    ) in result.capture


# -- Invalid group config is reported cleanly --


@pytest.mark.parametrize("cli_args", [(), ("--help",), ("other",)])
def test_task_duplicated_in_group_is_reported(run_poe, temp_pyproject, cli_args):
    """A task name used both at top level and in a group gives a clean error."""
    project_path = temp_pyproject(
        """
        [tool.poe]
        executor = "simple"
        [tool.poe.tasks]
        test = "poe_test_echo top"
        other = "poe_test_echo other"
        [tool.poe.groups.testing.tasks]
        test = "poe_test_echo grouped"
        """
    )
    result = run_poe(*cli_args, cwd=project_path)
    assert "Configured tasks:" in result.capture
    if cli_args == ("--help",):
        # --help hides config errors, but must not crash
        assert result.code == 0
        return
    assert result.code == 1
    assert "Error: Config from" in result.capture
    assert (
        "contains task 'test' multiple times, including in group testing"
        in result.capture
    )


@pytest.mark.parametrize("cli_args", [(), ("other",)])
def test_non_string_group_heading_is_reported(run_poe, temp_pyproject, cli_args):
    """A non-string group heading gives a clean validation error."""
    project_path = temp_pyproject(
        """
        [tool.poe]
        executor = "simple"
        [tool.poe.tasks]
        other = "poe_test_echo other"
        [tool.poe.groups.grp]
        heading = 5
        [tool.poe.groups.grp.tasks]
        grouped = "poe_test_echo grouped"
        """
    )
    result = run_poe(*cli_args, cwd=project_path)
    assert result.code == 1
    assert (
        "Error: Option 'groups.grp.heading' must have a value of type: str"
        in result.capture
    )
    assert "Configured tasks:\n  other" in result.capture
