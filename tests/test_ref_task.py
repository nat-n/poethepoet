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


def test_ref_interpolates_private_var_in_definition(run_poe_subproc):
    result = run_poe_subproc("greet-secret", project="refs")
    assert result.capture == "Poe => poe_test_echo hi secret\n"
    assert result.stdout == "hi secret\n"
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


def test_ref_bool_inheriting_flag(run_poe_subproc):
    """Ref task passes boolean args to referenced task via env inheritance"""
    result = run_poe_subproc("bool_ref_inheriting", "--flag", project="refs")
    assert result.stdout == "{'flag': True, 'val': True}\n"


def test_ref_bool_inheriting_defaults(run_poe_subproc):
    """Referenced task inherits typed False from ref's boolean args"""
    result = run_poe_subproc("bool_ref_inheriting", project="refs")
    assert result.stdout == "{'flag': False, 'val': True}\n"


def test_ref_bool_inheriting_negate(run_poe_subproc):
    """Negate a true-default boolean arg, verify False inherits through ref"""
    result = run_poe_subproc("bool_ref_inheriting", "--val", project="refs")
    assert result.stdout == "{'flag': False, 'val': False}\n"


def test_ref_child_arg_defaults_shadow_inherited_bool_args(run_poe_subproc):
    """Referenced task defaults override inherited values for matching arg names"""
    result = run_poe_subproc("bool_ref_forwarding", "--flag", project="refs")
    assert result.stdout.strip() == "unset:True"


def test_ref_child_defaults_override_inherited_negated_bool_arg(run_poe_subproc):
    """A child default still wins when the inherited value came from parent invocation"""
    result = run_poe_subproc("bool_ref_forwarding", "--val", project="refs")
    assert result.stdout.strip() == "unset:True"


def test_ref_definition_args_override_inherited_and_child_defaults(run_poe_subproc):
    """Args in the ref definition become child invocation args and win per name"""
    result = run_poe_subproc("bool_ref_override", "--flag", project="refs")
    assert result.stdout.strip() == "unset:unset"


def test_ref_child_arg_defaults_shadow_inherited_string_args(run_poe_subproc):
    """The same shadowing rule applies to non-boolean args"""
    result = run_poe_subproc(
        "word_ref_shadow",
        "--subject=parent-subject",
        "--tone=parent-tone",
        project="refs",
    )
    assert result.stdout.strip() == "child-subject:child-tone"


def test_ref_definition_args_override_inherited_string_args(run_poe_subproc):
    """Explicit args in the ref definition have higher precedence than inherited args"""
    result = run_poe_subproc(
        "word_ref_override",
        "--subject=parent-subject",
        "--tone=parent-tone",
        project="refs",
    )
    assert result.stdout.strip() == "child-subject:ref-tone"


def test_ref_child_multiple_arg_shadows_inherited_list(run_poe_subproc):
    """A child multiple arg shadows an inherited list, while other args still inherit"""
    result = run_poe_subproc(
        "multi_ref_shadow",
        "--items",
        "parent-a",
        "parent-b",
        "--label=parent-label",
        project="refs",
    )
    assert result.stdout == "{'items': None, 'label': 'parent-label'}\n"


def test_ref_definition_multiple_arg_overrides_inherited_list(run_poe_subproc):
    """Explicit list values in the ref definition override inherited multiple args"""
    result = run_poe_subproc(
        "multi_ref_override",
        "--items",
        "parent-a",
        "parent-b",
        "--label=parent-label",
        project="refs",
    )
    assert result.stdout == "{'items': ['ref-a', 'ref-b'], 'label': 'parent-label'}\n"


def test_ref_definition_empty_multiple_arg_overrides_inherited_list(run_poe_subproc):
    """An explicit empty multiple arg in the ref definition overrides an inherited list"""
    result = run_poe_subproc(
        "multi_ref_empty_override",
        "--items",
        "parent-a",
        "parent-b",
        "--label=parent-label",
        project="refs",
    )
    assert result.stdout == "{'items': [], 'label': 'parent-label'}\n"


def test_ref_bool_sequence_multilevel_flag(run_poe_subproc):
    """Sequence -> ref -> expr: boolean args survive two levels of inheritance"""
    result = run_poe_subproc("bool_sequence_ref", "--flag", project="refs")
    # cmd subtask sees True via env var, expr subtask sees True via typed arg
    assert "True:True" in result.stdout
    assert "{'flag': True, 'val': True}" in result.stdout


def test_ref_bool_sequence_multilevel_defaults(run_poe_subproc):
    """Sequence -> ref -> expr: False survives two levels of clone()"""
    result = run_poe_subproc("bool_sequence_ref", project="refs")
    assert "unset:True" in result.stdout
    assert "{'flag': False, 'val': True}" in result.stdout


def test_ref_bool_sequence_multilevel_negate(run_poe_subproc):
    """Sequence -> ref -> expr: negated True->False survives two levels"""
    result = run_poe_subproc("bool_sequence_ref", "--val", project="refs")
    assert "unset:unset" in result.stdout
    assert "{'flag': False, 'val': False}" in result.stdout


def test_ref_error_on_sequence_with_capture_stdout(run_poe_subproc):
    result = run_poe_subproc("capture-sequence", project="refs_error")
    assert "Error: Invalid task 'capture-sequence'" in result.capture
    assert (
        "Option 'capture_stdout' cannot be set on a ref task referencing 'sequence' "
        "task: 'do-sequence'"
    ) in result.capture

    assert result.stdout == ""
    assert result.stderr == ""
    assert not (result.path / "echo.txt").exists()
