import uuid


def test_ref_task(run_poe_subproc, projects, esc_prefix, is_windows):
    # This should be exactly the same as calling the echo task directly
    result = run_poe_subproc(
        "also_echo", "foo", "!", env={"POETRY_VIRTUALENVS_CREATE": "false"}
    )
    if is_windows:
        assert result.capture == (  # windows paths need quotes
            "Poe => poe_test_echo "
            f"'POE_ROOT:{projects['example']}' Password1, task_args: foo '!'\n"
        )
    else:
        assert result.capture == (
            "Poe => poe_test_echo "
            f"POE_ROOT:{projects['example']} Password1, task_args: foo '!'\n"
        )
    assert (
        result.stdout == f"POE_ROOT:{projects['example']} Password1, task_args: foo !\n"
    )
    assert result.stderr == ""


def test_ref_passes_named_args_in_definition(run_poe_subproc):
    result = run_poe_subproc("greet-dave", project="refs")
    assert result.capture == "Poe => poe_test_echo hi dave\n"
    assert result.stdout == "hi dave\n"
    assert result.stderr == ""


def test_ref_passes_extra_args_in_definition(run_poe_subproc):
    result = run_poe_subproc("greet-funny", project="refs")
    assert result.capture == "Poe => poe_test_echo hi 'lol!'\n"
    assert result.stdout == "hi lol!\n"
    assert result.stderr == ""


def test_ref_parses_named_args(run_poe_subproc):
    result = run_poe_subproc(
        "apologize", "--name=Davey", "--explain=Ah cannae dae that", project="refs"
    )
    assert (
        result.capture == """Poe => echo 'I'"'"'m sorry Davey, Ah cannae dae that'\n"""
    )
    assert result.stdout == "I'm sorry Davey, Ah cannae dae that\n"
    assert result.stderr == ""


def test_ref_forwards_arguments_if_none_defined(run_poe_subproc):
    result = run_poe_subproc(
        "say-sorry",
        "--name=Davey",
        "--explain=Ah cannae dae that",
        "--",
        ",",
        "anything",
        "else?",
        project="refs",
    )
    assert result.capture == (
        """Poe => echo 'I'"'"'m sorry Davey, Ah cannae dae that'"""
        """ , anything 'else?'\n"""
    )
    assert result.stdout == "I'm sorry Davey, Ah cannae dae that , anything else?\n"
    assert result.stderr == ""


def test_ref_forwards_arguments(run_poe_subproc):
    result = run_poe_subproc(
        "sorry-dave",
        "I",
        "cant",
        "do",
        "that",
        "--",
        "--",
        ",",
        "anything",
        "else?",
        project="refs",
    )
    assert (
        result.capture
        == """Poe => echo 'I'"'"'m sorry Dave, I cant do that' , anything 'else?'\n"""
    )
    assert result.stdout == "I'm sorry Dave, I cant do that , anything else?\n"
    assert result.stderr == ""

    # Pass extra args including -- if no args defined
    result = run_poe_subproc("greet-funny", "OK", project="refs")
    assert result.capture == "Poe => poe_test_echo hi 'lol!' OK\n"
    assert result.stdout == "hi lol! OK\n"
    assert result.stderr == ""


def test_ref_passes_capture_stdout(run_poe_subproc):
    arg = uuid.uuid4().hex
    result = run_poe_subproc("greet-ref-file", f"--subject={arg}", project="refs")
    assert result.capture == f"Poe <= poe_test_echo hi {arg}\n"
    assert result.stdout == ""
    assert result.stderr == ""
    assert (result.path / "greet-ref.txt").read_text() == f"hi {arg}\n"


def test_ref_passes_task_which_has_capture_stdout(run_poe_subproc):
    arg = uuid.uuid4().hex
    result = run_poe_subproc(
        "greet-ref-subject-file", f"--subject={arg}", project="refs"
    )
    assert result.capture == f"Poe <= poe_test_echo hi {arg}\n"
    assert result.stdout == ""
    assert result.stderr == ""
    assert (result.path / "greet.txt").read_text() == f"hi {arg}\n"


def test_ref_error_on_sequence_with_capture_stdout(run_poe_subproc):
    result = run_poe_subproc("capture-sequence", project="refs_error")
    assert "Error: Invalid task 'capture-sequence'" in result.capture
    assert (
        "Option 'capture_stdout' cannot be set on a ref task with: 'do-sequence'"
        in result.capture
    )
    assert result.stdout == ""
    assert result.stderr == ""
    assert not (result.path / "echo.txt").exists()
