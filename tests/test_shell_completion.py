def test_describe_tasks(run_poe_main):
    result = run_poe_main("_describe_tasks")
    # expect an ordered listing of non-hidden tasks defined in the dummy_project
    assert result.stdout == (
        "echo show_env greet greet-shouty count also_echo sing part1 composite_task "
        "also_composite_task greet-multiple travel\n"
    )
    assert result.stderr == ""


def test_list_tasks(run_poe_main):
    result = run_poe_main("_list_tasks")
    # expect an ordered listing of non-hidden tasks defined in the dummy_project
    assert result.stdout == (
        "echo show_env greet greet-shouty count also_echo sing part1 composite_task"
        " also_composite_task greet-multiple travel\n"
    )
    assert result.stderr == ""


def test_zsh_completion(run_poe_main):
    result = run_poe_main("_zsh_completion")
    # some lines to stdout and none for stderr
    assert len(result.stdout.split("\n")) > 5
    assert result.stderr == ""
    assert "Error: Unrecognised task" not in result.stdout


def test_bash_completion(run_poe_main):
    result = run_poe_main("_bash_completion")
    # some lines to stdout and none for stderr
    assert len(result.stdout.split("\n")) > 5
    assert result.stderr == ""
    assert "Error: Unrecognised task" not in result.stdout


def test_fish_completion(run_poe_main):
    result = run_poe_main("_fish_completion")
    # some lines to stdout and none for stderr
    assert len(result.stdout.split("\n")) > 5
    assert result.stderr == ""
    assert "Error: Unrecognised task" not in result.stdout
