import pytest
import re
from sys import version_info


@pytest.fixture(scope="session")
def setup_poetry_project(run_poetry, projects):
    run_poetry(["install"], cwd=projects["poetry_plugin"])


@pytest.fixture(scope="session")
def setup_poetry_project_empty_prefix(run_poetry, projects):
    run_poetry(["install"], cwd=projects["poetry_plugin/empty_prefix"].parent)


@pytest.mark.slow
@pytest.mark.skipif(version_info < (3, 7), reason="dependencies require python>=3.7")
def test_poetry_help(run_poetry, projects):
    result = run_poetry([], cwd=projects["poetry_plugin"])
    assert result.stdout.startswith("Poetry (version ")
    assert "poe cow-greet" in result.stdout
    assert re.search(r"\n  poe echo\s+It's like echo\n", result.stdout)
    # assert result.stderr == ""


@pytest.mark.slow
@pytest.mark.skipif(version_info < (3, 7), reason="dependencies require python>=3.7")
def test_task_with_cli_dependency(
    run_poetry, projects, setup_poetry_project, is_windows
):
    result = run_poetry(
        ["poe", "cow-greet", "yo yo yo"],
        cwd=projects["poetry_plugin"],
    )
    if is_windows:
        assert result.stdout.startswith("Poe => cowpy yo yo yo")
        assert "< yo yo yo >" in result.stdout
    else:
        # On POSIX cowpy expects notices its being called as a subprocess and tries
        # unproductively to take input from stdin
        assert result.stdout.startswith("Poe => cowpy yo yo yo")
        assert (
            "< Cowacter, eyes:default, tongue:False, thoughts:False >" in result.stdout
        )
    # assert result.stderr == ""


@pytest.mark.slow
@pytest.mark.skipif(version_info < (3, 7), reason="dependencies require python>=3.7")
def test_task_with_lib_dependency(
    run_poetry, projects, setup_poetry_project, is_windows
):
    result = run_poetry(["poe", "cow-cheese"], cwd=projects["poetry_plugin"])
    assert result.stdout == (
        "Poe => from cowpy import cow; print(list(cow.COWACTERS)[5])\ncheese\n"
    )
    # assert result.stderr == ""


@pytest.mark.slow
@pytest.mark.skipif(version_info < (3, 7), reason="dependencies require python>=3.7")
def test_task_accepts_any_args(run_poetry, projects, setup_poetry_project):
    result = run_poetry(
        ["poe", "echo", "--lol=:D", "--version", "--help"],
        cwd=projects["poetry_plugin"],
    )
    assert result.stdout == (
        "Poe => poe_test_echo --lol=:D --version --help\n--lol=:D --version --help\n"
    )
    # assert result.stderr == ""


@pytest.mark.slow
@pytest.mark.skipif(version_info < (3, 7), reason="dependencies require python>=3.7")
def test_poetry_help_without_poe_command_prefix(
    run_poetry, projects, setup_poetry_project_empty_prefix
):
    result = run_poetry([], cwd=projects["poetry_plugin/empty_prefix"].parent)
    assert result.stdout.startswith("Poetry (version ")
    assert "\n  cow-greet" in result.stdout
    assert "\n  echo               It's like echo\n" in result.stdout
    # assert result.stderr == ""


@pytest.mark.slow
@pytest.mark.skipif(version_info < (3, 7), reason="dependencies require python>=3.7")
def test_running_tasks_without_poe_command_prefix(
    run_poetry, projects, setup_poetry_project_empty_prefix
):
    result = run_poetry(
        ["echo", "--lol=:D", "--version", "--help"],
        cwd=projects["poetry_plugin/empty_prefix"].parent,
    )
    assert result.stdout == (
        "Poe => poe_test_echo --lol=:D --version --help\n--lol=:D --version --help\n"
    )
    # assert result.stderr == ""


@pytest.mark.slow
@pytest.mark.skipif(version_info < (3, 7), reason="dependencies require python>=3.7")
def test_running_poetry_command_with_hooks(run_poetry, projects, setup_poetry_project):
    result = run_poetry(["env", "info"], cwd=projects["poetry_plugin"])
    assert "THIS IS YOUR ENV!" in result.stdout
    assert "THAT WAS YOUR ENV!" in result.stdout
    # assert result.stderr == ""
