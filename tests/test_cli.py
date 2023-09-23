import re

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
    assert result.capture == "Poe => poe_test_env\n"
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

    assert re.search(
        r"CONFIGURED TASKS\n"
        r"  composite_task          \s+\n"
        r"  echo-args               \s+\n"
        r"  static-args-test        \s+\n"
        r"  call_attrs              \s+\n"
        r"  greet                   \s+\n"
        r"  async-task              \s+\n"
        r"    --a                   \s+\n"
        r"    --b                   \s+\n"
        r"  print-script-result     \s+\n"
        r"  dont-print-script-result\s+\n"
        r"  greet-passed-args       \s+\n"
        r"    --greeting            \s+\n"
        r"    --user                \s+\n"
        r"    --optional            \s+\n"
        r"    --upper               \s+\n"
        r"  greet-full-args         \s+\n"
        r"    --greeting, -g        \s+\[default: hi\]\n"
        r"    --user                \s+\n"
        r"    --upper               \s+\n"
        r"    --age, -a             \s+\n"
        r"    --height, -h          \s+The user's height in meters\n"
        r"  greet-strict            \s+All arguments are required\n"
        r"    --greeting"
        r"            \s+this one is required \[default: \$\{DOES\}n't \$\{STUFF\}\]\n"
        r"    --name                \s+and this one is required\n",
        result.capture,
    )
