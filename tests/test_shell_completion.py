def test_describe_tasks(run_poe_main):
    result = run_poe_main("_describe_tasks")
    # expect an ordered listing of non-hidden tasks defined in the dummy_project
    assert (
        result.stdout
        == "echo show_env greet greet-shouty count also_echo sing part1 composite_task also_composite_task\n"
    )
    assert result.stderr == ""
