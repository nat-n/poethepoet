from poethepoet import __version__


def test_call_no_args(run_poe):
    result = run_poe()

    assert result.capture.startswith(
        "Poe the Poet - A task runner that works well with poetry."
    ), "Output should start with poe header line"
    assert (
        "\nResult: No task specified.\n" in result.capture
    ), "Output should include status message"
    assert "CONFIGURED TASKS\n  echo" in result.capture, "echo task should be in help"


def test_call_with_root(run_poe, dummy_project_path):
    result = run_poe("--root", str(dummy_project_path), cwd=".")
    assert result.code == 1, "Expected non-zero result"
    assert result.capture.startswith(
        "Poe the Poet - A task runner that works well with poetry."
    ), "Output should start with poe header line"
    assert (
        "\nResult: No task specified.\n" in result.capture
    ), "Output should include status message"
    assert "CONFIGURED TASKS\n  echo" in result.capture, "echo task should be in help"


def test_call_unknown_task(run_poe):
    result = run_poe("not_a_task")
    assert result.code == 1, "Expected non-zero result"
    assert (
        "Error: Unrecognised task 'not_a_task'" in result.capture
    ), "Output should include error message"


def test_version_option(run_poe):
    result = run_poe("--version")
    assert result.code == 0, "Expected zero result"
    assert result.capture == f"Poe the poet - version: {__version__}\n"
    assert result.stdout == ""
    assert result.stderr == ""

    result = run_poe("--version", "-q")
    assert result.code == 0, "Expected zero result"
    assert result.capture == f"{__version__}\n"
    assert result.stdout == ""
    assert result.stderr == ""
