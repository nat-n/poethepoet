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
    assert result.stdout == ("here we go...\nThinking about and\nhello and hello\n")
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


def test_uses_private_var_filtered_from_subprocess(run_poe_subproc):
    """Private vars introduced via uses stay private in downstream subprocess envs"""
    result = run_poe_subproc("uses_private_env", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo hidden\n"
        "Poe <= poe_test_echo VISIBLE\n"
        "Poe <= poe_test_echo visible\n"
        "Poe => poe_test_env\n"
    )
    assert "_secret=hidden" not in result.stdout
    assert "_PUBLIC=VISIBLE" in result.stdout
    assert "normal=visible" in result.stdout
    assert result.stderr == ""


def test_uses_private_var_accessible_in_template(run_poe_subproc):
    """Private vars introduced via uses are still available for template resolution"""
    result = run_poe_subproc("uses_private_template", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo hidden\n"
        "Poe <= poe_test_echo VISIBLE\n"
        "Poe <= poe_test_echo visible\n"
        "Poe => poe_test_echo hidden:VISIBLE:visible\n"
    )
    assert result.stdout == "hidden:VISIBLE:visible\n"
    assert result.stderr == ""


def test_uses_private_var_inherited_and_filtered(run_poe_subproc):
    """Private vars introduced via uses stay private when inherited by subtasks"""
    result = run_poe_subproc("uses_private_inherited", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo hidden\n"
        "Poe <= poe_test_echo VISIBLE\n"
        "Poe <= poe_test_echo visible\n"
        "Poe => poe_test_env\n"
    )
    assert "_secret=hidden" not in result.stdout
    assert "_PUBLIC=VISIBLE" in result.stdout
    assert "normal=visible" in result.stdout
    assert result.stderr == ""


def test_uses_private_var_inherited_can_be_remapped_public(run_poe_subproc):
    """A child task can alias inherited private uses vars to public env vars via env"""
    result = run_poe_subproc("uses_private_remapped", project="graphs")
    assert result.capture == ("Poe <= poe_test_echo hidden\n" "Poe => poe_test_env\n")
    assert "_secret=hidden" not in result.stdout
    assert "public=hidden" in result.stdout
    assert result.stderr == ""
