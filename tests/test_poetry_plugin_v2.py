import os
import re

import pytest


@pytest.fixture(scope="module")
def _setup_poetry_project(run_poetry_2, projects):
    run_poetry_2(["install"], cwd=projects["poetry_plugin"])


@pytest.fixture(scope="module")
def _setup_poetry_project_empty_prefix(run_poetry_2, projects):
    run_poetry_2(
        ["install"],
        cwd=projects["poetry_plugin/empty_prefix"].parent,
    )


@pytest.fixture(scope="module")
def _setup_poetry_project_with_prefix(run_poetry_2, projects):
    run_poetry_2(
        ["install"],
        cwd=projects["poetry_plugin/with_prefix"].parent,
    )


@pytest.mark.slow
def test_poetry_help(run_poetry_2, projects):
    result = run_poetry_2([], cwd=projects["poetry_plugin"])
    assert result.stdout.startswith("Poetry (version ")
    assert "poe cow-greet" in result.stdout
    assert re.search(r"\n  poe echo\s+It's like echo\n", result.stdout)


# TODO: re-enable this test
@pytest.mark.skipif(
    os.environ.get("GITHUB_ACTIONS", "false") == "true",
    reason="Skipping test the doesn't seem to work in GitHub Actions lately",
)
@pytest.mark.slow
@pytest.mark.usefixtures("_setup_poetry_project")
def test_task_with_cli_dependency(run_poetry_2, projects, is_windows):
    result = run_poetry_2(
        ["poe", "cow-greet", "yo yo yo"],
        cwd=projects["poetry_plugin"],
    )
    if is_windows:
        assert result.stdout.startswith("Poe => cowpy 'yo yo yo'")
        assert "< yo yo yo >" in result.stdout
    else:
        # On POSIX cowpy expects notices its being called as a subprocess and tries
        # unproductively to take input from stdin
        assert result.stdout.startswith("Poe => cowpy 'yo yo yo'")
        assert (
            "< Cowacter, eyes:default, tongue:False, thoughts:False >" in result.stdout
        )


# TODO: re-enable this test
@pytest.mark.skipif(
    os.environ.get("GITHUB_ACTIONS", "false") == "true",
    reason="Skipping test the doesn't seem to work in GitHub Actions lately",
)
@pytest.mark.slow
@pytest.mark.usefixtures("_setup_poetry_project")
def test_task_with_lib_dependency(run_poetry_2, projects):
    result = run_poetry_2(["poe", "cow-cheese"], cwd=projects["poetry_plugin"])
    assert result.stdout == (
        "Poe => from cowpy import cow; print(list(cow.COWACTERS)[5])\ncheese\n"
    )


@pytest.mark.slow
@pytest.mark.usefixtures("_setup_poetry_project")
def test_task_accepts_any_args(run_poetry_2, projects):
    result = run_poetry_2(
        ["poe", "echo", "--lol=:D", "--version", "--help"],
        cwd=projects["poetry_plugin"],
    )
    assert result.stdout == (
        "Poe => poe_test_echo --lol=:D --version --help\n--lol=:D --version --help\n"
    )


@pytest.mark.slow
@pytest.mark.usefixtures("_setup_poetry_project_empty_prefix")
def test_poetry_help_without_poe_command_prefix(run_poetry_2, projects):
    result = run_poetry_2([], cwd=projects["poetry_plugin/empty_prefix"].parent)
    assert result.stdout.startswith("Poetry (version ")
    assert "\n  cow-greet" in result.stdout
    assert "\n  echo               It's like echo\n" in result.stdout
    assert "_secret_task" not in result.stdout


@pytest.mark.slow
@pytest.mark.usefixtures("_setup_poetry_project_empty_prefix")
def test_running_tasks_without_poe_command_prefix(run_poetry_2, projects):
    result = run_poetry_2(
        ["echo", "--lol=:D", "--version", "--help"],
        cwd=projects["poetry_plugin/empty_prefix"].parent,
    )
    assert result.stdout == (
        "Poe => poe_test_echo --lol=:D --version --help\n--lol=:D --version --help\n"
    )


@pytest.mark.slow
@pytest.mark.usefixtures("_setup_poetry_project_empty_prefix")
def test_poetry_command_from_included_file_with_empty_prefix(run_poetry_2, projects):
    result = run_poetry_2(
        ["included-greeting"],
        cwd=projects["poetry_plugin/empty_prefix"].parent,
    )
    assert result.stdout.startswith("Poe => echo 'Greetings from another file!'")


@pytest.mark.slow
@pytest.mark.usefixtures("_setup_poetry_project_empty_prefix")
def test_poetry_help_with_poe_command_prefix(run_poetry_2, projects):
    result = run_poetry_2([], cwd=projects["poetry_plugin/with_prefix"].parent)
    assert result.stdout.startswith("Poetry (version ")
    assert "\n  foo cow-greet" in result.stdout
    assert "\n  foo echo           It's like echo\n" in result.stdout
    assert "_secret_task" not in result.stdout


@pytest.mark.slow
@pytest.mark.usefixtures("_setup_poetry_project_with_prefix")
def test_running_tasks_with_poe_command_prefix(run_poetry_2, projects):
    result = run_poetry_2(
        ["foo", "echo", "--lol=:D", "--version", "--help"],
        cwd=projects["poetry_plugin/with_prefix"].parent,
    )
    assert result.stdout == (
        "Poe => poe_test_echo --lol=:D --version --help\n--lol=:D --version --help\n"
    )


@pytest.mark.slow
@pytest.mark.usefixtures("_setup_poetry_project_with_prefix")
def test_running_tasks_with_poe_command_prefix_missing_args(run_poetry_2, projects):
    result = run_poetry_2(
        ["foo"],
        cwd=projects["poetry_plugin/with_prefix"].parent,
    )
    assert "Usage:\n  poetry foo [global options]" in result.stdout


@pytest.mark.slow
@pytest.mark.usefixtures("_setup_poetry_project")
def test_running_poetry_command_with_hooks(run_poetry_2, projects):
    result = run_poetry_2(["env", "info"], cwd=projects["poetry_plugin"])
    assert "THIS IS YOUR ENV!" in result.stdout
    assert "THAT WAS YOUR ENV!" in result.stdout


@pytest.mark.slow
@pytest.mark.usefixtures("_setup_poetry_project")
def test_running_poetry_command_with_hooks_with_directory(run_poetry_2, projects):
    result = run_poetry_2(
        ["--directory=" + str(projects["poetry_plugin"]), "env", "info"],
        cwd=projects["poetry_plugin"].parent,
    )
    assert "THIS IS YOUR ENV!" in result.stdout
    assert "THAT WAS YOUR ENV!" in result.stdout


# TODO: re-enable this test
@pytest.mark.skipif(
    os.environ.get("GITHUB_ACTIONS", "false") == "true",
    reason="Skipping test the doesn't seem to work in GitHub Actions lately",
)
@pytest.mark.slow
@pytest.mark.usefixtures("_setup_poetry_project")
def test_task_with_cli_dependency_with_directory(run_poetry_2, projects, is_windows):
    result = run_poetry_2(
        [
            "--directory=" + str(projects["poetry_plugin"]),
            "poe",
            "cow-greet",
            "yo yo yo",
        ],
        cwd=projects["poetry_plugin"].parent,
    )
    if is_windows:
        assert result.stdout.startswith("Poe => cowpy 'yo yo yo'")
        assert "< yo yo yo >" in result.stdout
    else:
        # On POSIX cowpy expects notices its being called as a subprocess and tries
        # unproductively to take input from stdin
        assert result.stdout.startswith("Poe => cowpy 'yo yo yo'")
        assert (
            "< Cowacter, eyes:default, tongue:False, thoughts:False >" in result.stdout
        )


@pytest.mark.slow
@pytest.mark.parametrize("project_option", ["--directory", "-C", "-P"])
def test_running_task_with_project_option(run_poetry_2, projects, project_option):
    result = run_poetry_2(
        [project_option, "hooks", "poe", "say", "hello"],
        cwd=projects["poetry_plugin"],
    )
    assert "Unrecognized task" not in result.stdout
    assert "hello\n" in result.stdout
    assert result.code == 0


@pytest.mark.slow
def test_post_hook_not_run_after_failed_command(run_poetry_2, projects):
    # There's no lock file so `poetry check --lock` fails
    result = run_poetry_2(
        ["check", "--lock"], cwd=projects["poetry_plugin"] / "hooks"
    )
    assert "pre_check_hook" in result.stdout
    assert "post_check_hook" not in result.stdout
    assert result.code != 0


@pytest.mark.slow
@pytest.mark.parametrize(
    ("project_dir", "expected_error"),
    [
        (
            "conflicting_prefix",
            "error: poethepoet plugin: The configured command prefix 'build' "
            "conflicts with a poetry command.",
        ),
        (
            "conflicting_task",
            "error: poethepoet plugin: Poe task 'build' conflicts with a poetry "
            "command. Please rename the task or configure a command prefix.",
        ),
    ],
)
def test_plugin_config_errors_are_shown(
    run_poetry_2, projects, project_dir, expected_error
):
    result = run_poetry_2(["list"], cwd=projects["poetry_plugin"] / project_dir)
    assert expected_error in result.stderr
    assert "Set DEBUG_POE_PLUGIN=1 for details" not in result.stderr


@pytest.mark.slow
@pytest.mark.parametrize(
    ("verbosity_flag", "expect_task_header"),
    [("-v", False), ("-vv", True), ("-vvv", True)],
)
def test_poetry_verbosity_is_passed_to_poe(
    run_poetry_2, projects, verbosity_flag, expect_task_header
):
    # The hooks project sets a default poe verbosity of -2
    result = run_poetry_2(
        [verbosity_flag, "poe", "say", "hello"],
        cwd=projects["poetry_plugin"] / "hooks",
    )
    assert "hello\n" in result.stdout
    assert ("Poe => echo hello" in result.stdout) is expect_task_header


@pytest.mark.slow
def test_empty_argument_does_not_crash_poetry(run_poetry_2, projects):
    result = run_poetry_2([""], cwd=projects["poetry_plugin"] / "hooks")
    assert "string index out of range" not in result.stdout + result.stderr
    assert "IndexError" not in result.stdout + result.stderr
