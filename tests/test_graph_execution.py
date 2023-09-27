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


def test_uses_dry_run(run_poe_subproc):
    result = run_poe_subproc("-d", "deep-graph-with-args", project="graphs")
    assert result.capture == (
        "Poe => poe_test_echo here we go...\n"
        "Poe => :\n"
        "Poe <= poe_test_echo about\n"
        "Poe <= poe_test_echo hello\n"
        "Poe ?? unresolved dependency task results via uses option for task 'think'\n"
        "Poe ?? unresolved dependency task results via uses option for task"
        " 'deep-graph-with-args'\n"
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_task_graph_in_sequence(run_poe_subproc):
    result = run_poe_subproc("ab", project="graphs")
    assert result.capture == (
        "Poe <= echo A1\n"
        "Poe <= echo A2\n"
        "Poe => 'a1: ' + ${a1} + ', a2: ' + ${a2}\n"
        "Poe => echo b\n"
    )
    assert result.stdout == ("a1: A1, a2: A2\nb\n")
    assert result.stderr == ""
