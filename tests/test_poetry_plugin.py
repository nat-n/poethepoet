import pytest
from sys import version_info


@pytest.fixture(scope="session")
def setup_poetry_project(run_poetry, projects):
    run_poetry(
        ["config", "virtualenvs.in-project", "true"], cwd=projects["poetry_plugin"]
    )
    run_poetry(["install"], cwd=projects["poetry_plugin"])


@pytest.mark.slow
def test_poetry_help(run_poetry, projects):
    result = run_poetry([], cwd=projects["poetry_plugin"])
    assert result.stdout.startswith("Poetry (version ")
    assert "poe flask-version" in result.stdout
    assert "\n  poe echo           It's like echo" in result.stdout
    assert result.stderr == ""


@pytest.mark.slow
@pytest.mark.skipif(version_info < (3, 7), reason="dependencies require python>=3.7")
def test_has_dependencies(run_poetry, projects, setup_poetry_project):
    result = run_poetry(["poe", "flask-version"], cwd=projects["poetry_plugin"])
    assert result.stdout.startswith("Poe => flask --version")
    assert "Flask 1.0" in result.stdout
    assert result.stderr == ""


@pytest.mark.slow
def test_task_accepts_any_args(run_poetry, projects, setup_poetry_project):
    result = run_poetry(
        ["poe", "echo", "--lol=:D", "--version", "--help"],
        cwd=projects["poetry_plugin"],
    )
    assert result.stdout == (
        "Poe => echo --lol=:D --version --help\n--lol=:D --version --help\n"
    )
    assert result.stderr == ""


@pytest.mark.slow
def test_poetry_help_without_poe_command_prefix(
    run_poetry, projects, setup_poetry_project
):
    result = run_poetry([], cwd=projects["poetry_plugin/empty_prefix"].parent)
    assert result.stdout.startswith("Poetry (version ")
    assert "\n  flask-version" in result.stdout
    assert "\n  echo           It's like echo" in result.stdout
    assert result.stderr == ""


@pytest.mark.slow
def test_running_tasks_without_poe_command_prefix(
    run_poetry, projects, setup_poetry_project
):
    result = run_poetry(
        ["echo", "--lol=:D", "--version", "--help"],
        cwd=projects["poetry_plugin/empty_prefix"].parent,
    )
    assert result.stdout == (
        "Poe => echo --lol=:D --version --help\n--lol=:D --version --help\n"
    )
    assert result.stderr == ""
