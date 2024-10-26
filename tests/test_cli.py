import re

from poethepoet import __version__

# Setting POETRY_VIRTUALENVS_CREATE stops poetry from creating the virtualenv and
# spamming about it in stderr
poetry_vars = {"POETRY_VIRTUALENVS_CREATE": "false"}


def test_call_no_args(run_poe):
    result = run_poe()

    assert result.capture.startswith(
        "Poe the Poet - A task runner that works well with poetry."
    ), "Output should start with poe header line"
    assert (
        "\nResult: No task specified.\n" in result.capture
    ), "Output should include status message"
    assert "Configured tasks:\n  echo" in result.capture, "echo task should be in help"


def test_call_with_directory(run_poe, projects):
    result = run_poe("--directory", str(projects["example"]), cwd=".")
    assert result.code == 1, "Expected non-zero result"
    assert result.capture.startswith(
        "Poe the Poet - A task runner that works well with poetry."
    ), "Output should start with poe header line"
    assert (
        "\nResult: No task specified.\n" in result.capture
    ), "Output should include status message"
    assert (
        "Configured tasks:\n"
        "  echo                  It says what you say" in result.capture
    ), "echo task should be in help"


def test_call_with_directory_set_via_env(run_poe_subproc, projects):
    result = run_poe_subproc(env={"POE_PROJECT_DIR": str(projects["example"])}, cwd=".")
    assert result.code == 1, "Expected non-zero result"
    assert result.capture.startswith(
        "Poe the Poet - A task runner that works well with poetry."
    ), "Output should start with poe header line"
    assert (
        "\nResult: No task specified.\n" in result.capture
    ), "Output should include status message"
    assert (
        "Configured tasks:\n"
        "  echo                  It says what you say" in result.capture
    ), "echo task should be in help"


# Test legacy --root parameter (replaced by -C, --directory)
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
        "Configured tasks:\n"
        "  echo                  It says what you say" in result.capture
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
    assert result.capture.strip() == f"Poe the Poet - version: {__version__}"
    assert result.stdout == ""
    assert result.stderr == ""

    result = run_poe("--version", "-q")
    assert result.code == 0, "Expected zero result"
    assert result.capture.strip() == f"{__version__}"
    assert result.stdout == ""
    assert result.stderr == ""


def test_dry_run_cmd(run_poe_subproc):
    result = run_poe_subproc("-d", "show_env")
    assert result.capture == "Poe => poe_test_env\n"
    assert result.stdout == ""
    assert result.stderr == ""


def test_dry_run_script(run_poe_subproc):
    result = run_poe_subproc("-d", "multiple-lines-help", project="scripts")
    assert result.capture == "Poe => multiple-lines-help\n"
    assert result.stdout == ""
    assert result.stderr == ""


def test_pass_dry_run_and_verbosity_to_script(run_poe_subproc):
    result = run_poe_subproc("check-global-options", project="scripts")
    assert result.capture == "Poe => check-global-options\n"
    assert result.stdout == ("args ()\n" "kwargs {'dry': False, 'verbosity': '0'}\n")
    assert result.stderr == ""

    result = run_poe_subproc("-d", "check-global-options", project="scripts")
    assert result.capture == "Poe => check-global-options\n"
    assert result.stdout == ("args ()\n" "kwargs {'dry': True, 'verbosity': '0'}\n")
    assert result.stderr == ""

    result = run_poe_subproc("-d", "-v", "check-global-options", project="scripts")
    assert result.capture == "Poe => check-global-options\n"
    assert result.stdout == ("args ()\n" "kwargs {'dry': True, 'verbosity': '1'}\n")
    assert result.stderr == ""

    result = run_poe_subproc("-q", "check-global-options", project="scripts")
    assert result.capture == ""
    assert result.stdout == ("args ()\n" "kwargs {'dry': False, 'verbosity': '-1'}\n")
    assert result.stderr == ""


def test_poe_env_vars_are_set(run_poe_subproc):
    result = run_poe_subproc("show_env", env=poetry_vars)
    assert result.capture == "Poe => poe_test_env\n"
    for env_var in (
        "POE_VERBOSITY=0",
        "POE_CONF_DIR=",
        "POE_ACTIVE=poetry",
        "POE_CWD=",
        "POE_ROOT=",
        "POE_PWD=",
    ):
        assert env_var in result.stdout


def test_documentation_of_task_named_args(run_poe):
    result = run_poe(project="scripts")
    assert result.capture.startswith(
        "Poe the Poet - A task runner that works well with poetry."
    ), "Output should start with poe header line"
    assert (
        "\nResult: No task specified.\n" in result.capture
    ), "Output should include status message"

    assert re.search(
        r"Configured tasks:\n"
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
        r"    --name"
        r"            \s+and this one is required\n"
        r"  greet-positional        \s+\n"
        r"    greeting"
        r"            \s+this one is required \[default: \$\{DEFAULT_GREETING\}\]\n"
        r"    user"
        r"            \s+and this one is required\n"
        r"    --upper               \s+\n"
        r"  multiple-value-args     \s+\n"
        r"    first                 \s+\n"
        r"    second                \s+\n"
        r"    --widgets             \s+\n"
        r"    --engines             \s+\n"
        r"  multiple-lines-help     \s+Multilines\n"
        r"                            \s+Creating multi-line documentation for greater"
        " detail and inclusion of examples\n"
        r"    first                 \s+First positional arg\n"
        r"                            \s+documentation multiline\n"
        r"    second                \s+Multiple positional arg\n"
        r"                            \s+documentation multiline\n"
        r"    --widgets             \s+Multiple arg\n"
        r"                            \s+documentation multiline\n"
        r"    --engines             \s+Default arg\n"
        r"                            \s+documentation multiline\s+\n"
        r"                          \s+\[default: true\]\n",
        result.capture,
    )
