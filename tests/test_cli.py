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


def test_call_with_root(run_poe, projects):
    result = run_poe("--root", str(projects["example"]), cwd=".")
    assert result.code == 1, "Expected non-zero result"
    assert result.capture.startswith(
        "Poe the Poet - A task runner that works well with poetry."
    ), "Output should start with poe header line"
    assert (
        "\nResult: No task specified.\n" in result.capture
    ), "Output should include status message"
    assert (
        "CONFIGURED TASKS\n  echo                 It says what you say"
        in result.capture
    ), "echo task should be in help"


def test_call_unknown_task(run_poe):
    result = run_poe("not_a_task")
    assert result.code == 1, "Expected non-zero result"
    assert (
        "Error: Unrecognised task 'not_a_task'" in result.capture
    ), "Output should include error message"


def test_call_hidden_task(run_poe):
    result = run_poe("_part2")
    assert result.code == 1, "Expected non-zero result"
    assert (
        "Error: Tasks prefixed with `_` cannot be executed directly" in result.capture
    ), "Output should include error message"
    assert (
        "Poe => " not in result.capture
    ), "Output should not look like a successful execution"


def test_version_option(run_poe):
    result = run_poe("--version")
    assert result.code == 0, "Expected zero result"
    assert result.capture.strip() == f"Poe the poet - version: {__version__}"
    assert result.stdout == ""
    assert result.stderr == ""

    result = run_poe("--version", "-q")
    assert result.code == 0, "Expected zero result"
    assert result.capture.strip() == f"{__version__}"
    assert result.stdout == ""
    assert result.stderr == ""


def test_dry_run(run_poe_subproc):
    result = run_poe_subproc("-d", "show_env")
    assert result.capture == f"Poe => env\n"
    assert result.stdout == ""
    assert result.stderr == ""


def test_documentation_of_task_named_args(run_poe):
    result = run_poe(project="scripts")
    assert result.capture.startswith(
        "Poe the Poet - A task runner that works well with poetry."
    ), "Output should start with poe header line"
    assert (
        "\nResult: No task specified.\n" in result.capture
    ), "Output should include status message"
    assert (
        "CONFIGURED TASKS\n"
        "  composite_task     \n"
        "  echo-args          \n"
        "  static-args-test   \n"
        "  call_attrs         \n"
        "  greet              \n"
        "  greet-passed-args  \n"
        "    --greeting       \n"
        "    --user           \n"
        "    --optional       \n"
        "    --upper          \n"
        "  greet-full-args    \n"
        "    --greeting, -g   \n"
        "    --user           \n"
        "    --upper          \n"
        "    --age, -a        \n"
        "    --height, -h     The user's height in meters\n"
        "  greet-strict       All arguments are required\n"
        "    --greeting       this one is required\n"
        "    --name           and this one is required\n"
    ) in result.capture
