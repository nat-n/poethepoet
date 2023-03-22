def test_ref_passes_named_args_in_definition(run_poe_subproc):
    result = run_poe_subproc("greet-dave", project="refs")
    assert result.capture == "Poe => poe_test_echo hi dave\n"
    assert result.stdout == "hi dave\n"
    assert result.stderr == ""


def test_ref_passes_extra_args_in_definition(run_poe_subproc):
    result = run_poe_subproc("greet-funny", project="refs")
    assert result.capture == "Poe => poe_test_echo hi lol!\n"
    assert result.stdout == "hi lol!\n"
    assert result.stderr == ""
