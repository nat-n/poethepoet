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
