def test_call_attr_func(run_poe_subproc):
    result = run_poe_subproc("deep-graph-with-args", project="graphs")
    assert result.capture == (
        "Poe => poe_test_echo here we go...\n"
        "Poe => :\n"
        "Poe <= poe_test_echo about\n"
        "Poe <= poe_test_echo hello\n"
        "Poe => poe_test_echo Thinking about and\n"
        "Poe => poe_test_echo hello and hello\n"
    )
    assert result.stdout == (
        "here we go...\n" "Thinking about and\n" "hello and hello\n"
    )
    assert result.stderr == ""
