def test_call_attr_func(run_poe_subproc):
    result = run_poe_subproc("deep-graph-with-args", project="graphs")
    assert result.capture == (
        "Poe => echo here we go...\n"
        "Poe => :\n"
        "Poe => echo about\n"
        "Poe => echo hello\n"
        "Poe => echo Thinking about and\n"
        "Poe => echo hello and hello\n"
    )
    assert result.stdout == (
        "here we go...\n" "Thinking about and\n" "hello and hello\n"
    )
    assert result.stderr == ""
