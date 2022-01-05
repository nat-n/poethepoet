def test_docs_for_include_toml_file(run_poe_subproc):
    result = run_poe_subproc(project="includes")
    assert (
        "CONFIGURED TASKS\n"
        "  echo           says what you say\n"
        "  greet          \n"
        "  greet1         \n"
        "  greet2         Issue a greeting from the Iberian Peninsula\n"
    ) in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_run_task_included_from_toml_file(run_poe_subproc):
    result = run_poe_subproc("greet", "Whirl!", project="includes")
    assert result.capture == "Poe => echo Hello Whirl!\n"
    assert result.stdout == "Hello Whirl!\n"
    assert result.stderr == ""


def test_run_task_not_included_from_toml_file(run_poe_subproc):
    result = run_poe_subproc("echo", "Whirl!", project="includes")
    assert result.capture == "Poe => echo Whirl!\n"
    assert result.stdout == "Whirl!\n"
    assert result.stderr == ""


def test_docs_for_multiple_includes(run_poe_subproc, projects):
    result = run_poe_subproc(
        f'--root={projects["includes/multiple_includes"]}',
    )
    assert (
        "CONFIGURED TASKS\n"
        "  echo           says what you say\n"
        "  greet          \n"
        "  greet1         \n"
        "  greet2         Issue a greeting from the Iberian Peninsula\n"
        "  laugh          a mirthful task\n"
    ) in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_running_from_multiple_includes(run_poe_subproc, projects):
    result = run_poe_subproc(
        f'--root={projects["includes/multiple_includes"]}',
        "echo",
        "Whirl!",
        project="includes",
    )
    assert result.capture == "Poe => echo Whirl!\n"
    assert result.stdout == "Whirl!\n"
    assert result.stderr == ""

    result = run_poe_subproc(
        f'--root={projects["includes/multiple_includes"]}', "greet", "Whirl!"
    )
    assert result.capture == "Poe => echo Hello Whirl!\n"
    assert result.stdout == "Hello Whirl!\n"
    assert result.stderr == ""

    result = run_poe_subproc(
        f'--root={projects["includes/multiple_includes"]}', "laugh"
    )
    assert result.capture == "Poe => echo $ONE_LAUGH | tr a-z A-Z\n"
    assert result.stdout == "LOL\n"
    assert result.stderr == ""
