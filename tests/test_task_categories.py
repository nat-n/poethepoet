"""Tests for task category grouping feature."""


def test_categories_in_help_output(run_poe_subproc, projects):
    """Test that tasks are grouped by category in help output."""
    result = run_poe_subproc(cwd=projects["categories"])
    assert result.code == 1, "Expected non-zero result when no task specified"

    output = result.capture

    assert "auth" in output, "Should contain 'auth' category"
    assert "docker" in output, "Should contain 'docker' category"
    assert "static_typing" in output, "Should contain 'static_typing' category"

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
    empty_category_idx = tasks_section.find("empty_category")
    assert uncategorized_idx > 0, "Should have uncategorized task"
    assert another_uncategorized_idx > 0, "Should have another_uncategorized task"
    assert empty_category_idx > 0, "Should have empty_category task"

    auth_category_idx = tasks_section.find("  auth")
    aws_login_idx = tasks_section.find("aws_login")
    assert auth_category_idx > 0, "Should have 'auth' category header"
    assert (
        aws_login_idx > auth_category_idx
    ), "aws_login should appear after auth category"

    docker_category_idx = tasks_section.find("  docker")
    docker_start_idx = tasks_section.find("docker_start")
    docker_stop_idx = tasks_section.find("docker_stop")
    assert docker_category_idx > 0, "Should have 'docker' category header"
    assert (
        docker_start_idx > docker_category_idx
    ), "docker_start should appear after docker category"
    assert (
        docker_stop_idx > docker_category_idx
    ), "docker_stop should appear after docker category"

    static_typing_category_idx = tasks_section.find("  static_typing")
    check_idx = tasks_section.find("check")
    assert static_typing_category_idx > 0, "Should have 'static_typing' category header"
    assert (
        check_idx > static_typing_category_idx
    ), "check should appear after static_typing category"

    assert (
        auth_category_idx < docker_category_idx < static_typing_category_idx
    ), "Categories should be sorted alphabetically"


def test_task_execution_with_category(run_poe_subproc, projects):
    """Test that tasks with categories can still be executed normally."""
    result = run_poe_subproc("check", cwd=projects["categories"])
    assert result.code == 0, "Task execution should succeed"
    assert "Running mypy..." in result.capture, "Should execute the check task"


def test_empty_string_category_treated_as_uncategorized(run_poe_subproc, projects):
    """Test that tasks with category='' are treated same as no category."""
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
    empty_category_line_idx = None
    first_category_line_idx = None

    for i, line in enumerate(tasks_section_lines):
        if "uncategorized" in line and uncategorized_line_idx is None:
            uncategorized_line_idx = i
        if "empty_category" in line:
            empty_category_line_idx = i
        is_category_line = (
            line.strip()
            and not line.startswith("    ")
            and ("auth" in line or "docker" in line or "static_typing" in line)
        )
        if (
            is_category_line
            and first_category_line_idx is None
            and "Configured tasks" not in line
        ):
            first_category_line_idx = i

    assert uncategorized_line_idx is not None, "Should have uncategorized task"
    assert empty_category_line_idx is not None, "Should have empty_category task"
    assert first_category_line_idx is not None, "Should have at least one category"

    assert (
        uncategorized_line_idx < first_category_line_idx
    ), "uncategorized task should appear before categories"
    assert (
        empty_category_line_idx < first_category_line_idx
    ), "empty_category task should appear before categories (treated as uncategorized)"


def test_mixed_categorized_and_uncategorized_tasks(run_poe_subproc, projects):
    """Test that both categorized and uncategorized tasks appear correctly."""
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
    first_category_line_idx = None

    for i, line in enumerate(tasks_section_lines):
        if (
            "uncategorized" in line or "another_uncategorized" in line
        ) and uncategorized_line_idx is None:
            uncategorized_line_idx = i
        is_category_line = (
            line.strip()
            and not line.startswith("    ")
            and ("auth" in line or "docker" in line or "static_typing" in line)
        )
        if (
            is_category_line
            and first_category_line_idx is None
            and "Configured tasks" not in line
        ):
            first_category_line_idx = i

    if uncategorized_line_idx is not None and first_category_line_idx is not None:
        assert (
            uncategorized_line_idx < first_category_line_idx
        ), "Uncategorized tasks should appear before categorized tasks"
