import re

import pytest

# Setting POETRY_VIRTUALENVS_CREATE stops poetry from creating the virtualenv and
# spamming about it in stderr
poetry_vars = {"POETRY_VIRTUALENVS_CREATE": "false"}


def test_setting_default_task_type(run_poe_subproc, projects, esc_prefix):
    # Also tests passing of extra_args to sys.argv
    result = run_poe_subproc(
        "echo-args",
        "nat,",
        r"welcome to " + esc_prefix + "${POE_ROOT}",
        project="scripts",
        env=poetry_vars,
        shell=True,
    )
    assert (
        result.capture == f"Poe => echo-args nat, 'welcome to {projects['scripts']}'\n"
    )
    assert result.stdout == f"hello nat, welcome to {projects['scripts']}\n"
    result.assert_no_err()


def test_setting_default_array_item_task_type(run_poe):
    result = run_poe(
        "composite_task", project="scripts", env={"POETRY_VIRTUALENVS_CREATE": "false"}
    )
    assert (
        result.capture == "Poe => poe_test_echo Hello\nPoe => poe_test_echo 'World!'\n"
    )
    assert result.stdout == "Hello\nWorld!\n"
    result.assert_no_err()


def test_setting_global_env_vars(run_poe):
    result = run_poe("travel", env=poetry_vars)
    assert (
        result.capture == "Poe => poe_test_echo 'from EARTH to'\nPoe => 'travel[1]'\n"
    )
    assert result.stdout == "from EARTH to\nMARS\n"
    result.assert_no_err()


def test_setting_default_verbosity(run_poe, low_verbosity_project_path):
    result = run_poe(
        "test",
        cwd=low_verbosity_project_path,
    )
    assert result.capture == ""
    assert result.stdout == "Hello there!\n"
    result.assert_no_err()


def test_override_default_verbosity(run_poe, low_verbosity_project_path):
    result = run_poe(
        "-v",
        "-v",
        "test",
        cwd=low_verbosity_project_path,
    )
    assert result.capture == "Poe => poe_test_echo Hello 'there!'\n"
    assert result.stdout == "Hello there!\n"
    result.assert_no_err()


def test_partially_decrease_verbosity(run_poe, high_verbosity_project_path):
    result = run_poe(
        "-q",
        "test",
        cwd=high_verbosity_project_path,
    )
    assert result.capture == "Poe => poe_test_echo Hello 'there!'\n"
    assert result.stdout == "Hello there!\n"
    result.assert_no_err()


def test_decrease_verbosity(run_poe):
    result = run_poe("-q", "part1", env=poetry_vars)
    assert result.capture == ""
    assert result.stdout == "Hello\n"
    result.assert_no_err()


@pytest.mark.parametrize("filename", ["poe_tasks.yaml", "poe_tasks.toml"])
def test_empty_config_file_has_no_tasks(run_poe, tmp_path, filename):
    tmp_path.joinpath(filename).write_text("")
    result = run_poe(cwd=tmp_path)
    assert result.code == 1
    assert "Error:" not in result.capture
    assert "NO TASKS CONFIGURED" in result.capture


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("poe_tasks.json", "[1, 2]"),
        ("poe_tasks.json", '"hello"'),
        ("poe_tasks.yaml", "hello"),
        ("poe_tasks.yaml", "- a\n- b\n"),
    ],
)
def test_config_file_without_top_level_table(run_poe, tmp_path, filename, content):
    config_path = tmp_path.joinpath(filename)
    config_path.write_text(content)
    result = run_poe("a", cwd=tmp_path)
    assert result.code == 1
    assert (
        f"Error: Config file at {config_path} must contain a table at the top level"
        in result.capture
    )


@pytest.mark.parametrize(
    ("content", "expected_error"),
    [
        ('[tool]\npoe = "foo"\n', "Option 'tool.poe' must be a table"),
        ('[tool.poe]\ntasks = "foo"\n', "Option 'tasks' must be a dict"),
        ('[tool.poe.groups]\ng = "foo"\n', "Option 'groups.g' must be a dict"),
        (
            '[tool.poe.groups.g]\ntasks = "foo"\n',
            "Option 'groups.g.tasks' must be a dict",
        ),
    ],
)
def test_pyproject_with_non_table_poe_config(temp_pyproject, content, expected_error):
    # Checked at the config level, since the CLI output for these cases also
    # depends on help rendering tolerating the invalid config
    from poethepoet.config import PoeConfig
    from poethepoet.exceptions import ConfigValidationError

    project_path = temp_pyproject(content)
    with pytest.raises(ConfigValidationError, match=re.escape(expected_error)):
        PoeConfig(cwd=project_path).load_sync()


@pytest.mark.parametrize(
    ("filename", "content"),
    [("empty.yaml", ""), ("list.json", "[1, 2]"), ("scalar.yaml", "hello")],
)
def test_include_file_without_top_level_table(
    run_poe, temp_pyproject, filename, content
):
    project_path = temp_pyproject(
        f"""
        [tool.poe]
        executor = "simple"
        include = "{filename}"
        [tool.poe.tasks]
        a = "poe_test_echo a"
        """
    )
    project_path.joinpath(filename).write_text(content)
    result = run_poe("a", cwd=project_path)
    if not content:
        assert result.code == 0
        assert result.stdout == "a\n"
        return
    assert result.code == 1
    assert (
        f"Error: Config file at {project_path / filename} must contain a table"
        in result.capture
    )
    assert "at the top level" in result.capture


@pytest.mark.parametrize(
    ("filename", "content", "file_format", "detail"),
    [
        ("pyproject.toml", "[tool.poe.tasks]\na = \n", "toml", "line 2, column 5"),
        ("poe_tasks.toml", "a = \n", "toml", "line 1, column 5"),
        ("poe_tasks.json", '{"tasks": }', "json", "line 1 column 11"),
        ("poe_tasks.yaml", "tasks: [\n", "yaml", "line 2, column 1"),
        ("poe_tasks.yaml", 'tasks:\n  a: "echo\n', "yaml", "line 3, column 1"),
        ("poe_tasks.yml", "tasks:\n\ta: echo\n", "yaml", "line 2, column 1"),
    ],
)
def test_malformed_config_file(
    run_poe, tmp_path, filename, content, file_format, detail
):
    config_path = tmp_path.joinpath(filename)
    config_path.write_text(content)
    result = run_poe("a", cwd=tmp_path)
    assert result.code == 1
    assert (
        f"Error: Couldn't parse {file_format} file at {config_path}: " in result.capture
    )
    assert detail in result.capture
    assert "Couldn't open file" not in result.capture
    assert "From: " not in result.capture


@pytest.mark.parametrize(
    ("filename", "content", "file_format"),
    [
        ("broken.toml", "a = \n", "toml"),
        ("broken.json", '{"tasks": }', "json"),
        ("broken.yml", "tasks: [\n", "yaml"),
    ],
)
def test_malformed_include_file(
    run_poe, temp_pyproject, filename, content, file_format
):
    project_path = temp_pyproject(
        f"""
        [tool.poe]
        include = "{filename}"
        [tool.poe.tasks]
        a = "poe_test_echo a"
        """
    )
    project_path.joinpath(filename).write_text(content)
    result = run_poe("a", cwd=project_path)
    assert result.code == 1
    assert (
        f"Error: Couldn't parse {file_format} file at {project_path / filename}: "
        in result.capture
    )
    assert "From: " not in result.capture


def test_unreadable_include_file(run_poe, temp_pyproject):
    project_path = temp_pyproject(
        """
        [tool.poe]
        include = "tasks.toml"
        [tool.poe.tasks]
        a = "poe_test_echo a"
        """
    )
    project_path.joinpath("tasks.toml").mkdir()
    result = run_poe("a", cwd=project_path)
    assert result.code == 1
    assert (
        f"Error: Couldn't open file at {project_path / 'tasks.toml'}: "
        in result.capture
    )
