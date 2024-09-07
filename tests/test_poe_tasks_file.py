def test_prefer_valid_pyproject(run_poe_subproc, projects):
    # and import the poe_tasks from elsewhere
    result = run_poe_subproc(project="poe_tasks_file")
    assert (
        "Configured tasks:\n"
        "  main_pyproject        \n"
        "  main_poetasks_toml    \n"
        "  sub1_poetasks_toml    \n"
        "  sub1_poetasks_yaml    \n"
        "  sub1_poetasks_json    \n"
        "  sub2_poetasks_yaml    \n"
        "  sub2_poetasks_json    \n"
        "  sub3_poetasks_json    \n\n"
    ) in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_prefer_poe_tasks_toml_over_yaml_or_invalid_pyproject(
    run_poe_subproc, projects
):
    result = run_poe_subproc(cwd=projects["poe_tasks_file"] / "sub1")
    assert ("Configured tasks:\n  sub1_poetasks_toml    \n\n") in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_prefer_poe_tasks_yaml_over_json(run_poe_subproc, projects):
    # and import local pyproject.toml
    # and use full tool.poe namespace for file contents
    result = run_poe_subproc(cwd=projects["poe_tasks_file"] / "sub2")
    assert ("Configured tasks:\n  sub2_poetasks_yaml    \n\n") in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_load_poe_tasks_json(run_poe_subproc, projects):
    # and don't namespace file contents
    # and import tasks from another directory
    result = run_poe_subproc(cwd=projects["poe_tasks_file"] / "sub3")
    assert (
        "Configured tasks:\n"
        "  sub3_poetasks_json    \n"
        "  sub2_poetasks_yaml    \n\n"
    ) in result.capture
    assert result.stdout == ""
    assert result.stderr == ""
