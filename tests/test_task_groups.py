"""Tests for task grouping feature."""

# -- Help output tests --


def test_groups_in_help_output(run_poe_subproc, projects):
    """Test that tasks are grouped correctly in help output."""
    result = run_poe_subproc(cwd=projects["groups"])
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


# -- Task execution from groups --


def test_task_execution_from_group(run_poe_subproc, projects):
    """Tasks defined in groups can be executed normally."""
    result = run_poe_subproc("check", cwd=projects["groups"])
    assert result.code == 0
    assert "Running mypy..." in result.capture


# -- Group executor inheritance tests --


def test_group_executor_inherited(run_poe_subproc, projects):
    """Task with no executor in a group with executor='simple' should use simple."""
    result = run_poe_subproc("group_show_env", cwd=projects["groups"])
    assert result.code == 0
    assert "POE_ACTIVE=simple" in result.stdout


def test_group_executor_inherited_fails_with_bad_config(run_poe_subproc, projects):
    """Task inheriting a virtualenv executor with a missing venv should fail."""
    result = run_poe_subproc("venv_group_task", cwd=projects["groups"])
    assert result.code == 1
    assert "nonexistent_venv" in result.capture


def test_group_executor_overridden_by_task(run_poe_subproc, projects):
    """Task-level executor overrides group-level executor."""
    result = run_poe_subproc("venv_group_task_override", cwd=projects["groups"])
    assert result.code == 0
    assert "override_works" in result.stdout


def test_group_executor_overridden_by_cli(run_poe_subproc, projects):
    """CLI --executor overrides group-level executor."""
    result = run_poe_subproc(
        "--executor", "simple", "venv_group_task", cwd=projects["groups"]
    )
    assert result.code == 0
