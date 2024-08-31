import pytest


def test_customize_program_name(run_poe, projects):
    result = run_poe(program_name="boop")
    assert "Usage:\n  boop [global options] task" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_bad_args_doc_with_custom_program_name(run_poe, projects, capsys):
    with pytest.raises(SystemExit):
        result = run_poe("async-task", "--fail", program_name="boop", project="scripts")
    result = capsys.readouterr()
    assert result.out == ""
    assert result.err == (
        "usage: boop async-task [--a A] [--b B]\n"
        "boop async-task: error: unrecognized arguments: --fail\n"
    )


def test_customize_config_name(run_poe, projects, capsys):
    result = run_poe("hello", config_name="tasks.toml", project="custom_config")
    assert result.capture == "Poe => poe_test_echo hello from tasks.toml\n"
    assert result.stdout == ""
    assert result.stderr == ""


def test_customize_config_name_with_json(run_poe, projects, capsys):
    result = run_poe("hello", config_name="tasks.json", project="custom_config")
    assert result.capture == "Poe => poe_test_echo hello from tasks.json\n"
    assert result.stdout == ""
    assert result.stderr == ""

    result = run_poe(
        "-C",
        str(projects["custom_config"]),
        "hello",
        config_name="tasks.json",
    )
    assert result.capture == "Poe => poe_test_echo hello from tasks.json\n"
    assert result.stdout == ""
    assert result.stderr == ""
