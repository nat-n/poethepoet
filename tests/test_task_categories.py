"""Tests for task grouping feature."""


def test_groups_in_help_output(run_poe_subproc, projects):
    """Test that tasks are grouped by their group in help output."""
    result = run_poe_subproc(cwd=projects["categories"])
    assert result.code == 1, "Expected non-zero result when no task specified"

    output = result.capture

    assert "Authentication" in output, "Should contain 'Authentication' heading"
    assert "Docker" in output, "Should contain 'Docker' heading"
    assert "Static Typing" in output, "Should contain 'Static Typing' heading"

    lines = output.split("\n")
    configured_tasks_idx = None
    for i, line in enumerate(lines):
        if "Configured tasks:" in line:
            configured_tasks_idx = i
            break

    assert configured_tasks_idx is not None, "Should have 'Configured tasks:' section"

    tasks_section = "\n".join(lines[configured_tasks_idx:])

    uncategorized_idx = tasks_section.find("uncategorized")
    another_uncategorized_idx = tasks_section.find("another_uncategorized")
    assert uncategorized_idx > 0, "Should have uncategorized task"
    assert another_uncategorized_idx > 0, "Should have another_uncategorized task"

    auth_heading_idx = tasks_section.find("  Authentication")
    aws_login_idx = tasks_section.find("aws_login")
    assert auth_heading_idx > 0, "Should have 'Authentication' group heading"
    assert (
        aws_login_idx > auth_heading_idx
    ), "aws_login should appear after Authentication heading"

    docker_heading_idx = tasks_section.find("  Docker")
    docker_start_idx = tasks_section.find("docker_start")
    docker_stop_idx = tasks_section.find("docker_stop")
    assert docker_heading_idx > 0, "Should have 'Docker' group heading"
    assert (
        docker_start_idx > docker_heading_idx
    ), "docker_start should appear after Docker heading"
    assert (
        docker_stop_idx > docker_heading_idx
    ), "docker_stop should appear after Docker heading"

    static_typing_heading_idx = tasks_section.find("  Static Typing")
    check_idx = tasks_section.find("check")
    assert static_typing_heading_idx > 0, "Should have 'Static Typing' group heading"
    assert (
        check_idx > static_typing_heading_idx
    ), "check should appear after Static Typing heading"

    assert (
        auth_heading_idx < docker_heading_idx < static_typing_heading_idx
    ), "Groups should be sorted alphabetically by heading"


def test_task_execution_from_group(run_poe_subproc, projects):
    """Test that tasks defined in groups can still be executed normally."""
    result = run_poe_subproc("check", cwd=projects["categories"])
    assert result.code == 0, "Task execution should succeed"
    assert "Running mypy..." in result.capture, "Should execute the check task"


def test_mixed_grouped_and_ungrouped_tasks(run_poe_subproc, projects):
    """Test that both grouped and ungrouped tasks appear correctly."""
    result = run_poe_subproc(cwd=projects["categories"])

    output = result.capture
    lines = output.split("\n")

    configured_tasks_idx = None
    for i, line in enumerate(lines):
        if "Configured tasks:" in line:
            configured_tasks_idx = i
            break

    assert configured_tasks_idx is not None
    tasks_section_lines = lines[configured_tasks_idx:]

    uncategorized_line_idx = None
    first_group_line_idx = None

    for i, line in enumerate(tasks_section_lines):
        if (
            "uncategorized" in line or "another_uncategorized" in line
        ) and uncategorized_line_idx is None:
            uncategorized_line_idx = i
        is_group_line = (
            line.strip()
            and not line.startswith("    ")
            and (
                "Authentication" in line or "Docker" in line or "Static Typing" in line
            )
        )
        if (
            is_group_line
            and first_group_line_idx is None
            and "Configured tasks" not in line
        ):
            first_group_line_idx = i

    assert uncategorized_line_idx is not None, "Should have uncategorized task"
    assert first_group_line_idx is not None, "Should have at least one group"

    assert (
        uncategorized_line_idx < first_group_line_idx
    ), "Ungrouped tasks should appear before grouped tasks"


def test_group_heading_display(run_poe_subproc, projects):
    """Test that group headings are displayed instead of group names."""
    result = run_poe_subproc(cwd=projects["categories"])

    output = result.capture

    assert "Static Typing" in output, "Should display 'Static Typing' heading"
    assert "Authentication" in output, "Should display 'Authentication' heading"
    assert "Docker" in output, "Should display 'Docker' heading"

    lines = output.split("\n")
    tasks_section_started = False
    for line in lines:
        if "Configured tasks:" in line:
            tasks_section_started = True
            continue
        if tasks_section_started and line.strip().startswith("static_typing"):
            raise AssertionError("Should use heading 'Static Typing', not group name")
