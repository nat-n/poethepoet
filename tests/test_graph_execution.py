def test_call_attr_func(run_poe):
    result = run_poe("deep-graph-with-args", project="graphs")
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


def test_uses_dry_run(run_poe):
    result = run_poe("-d", "deep-graph-with-args", project="graphs")
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


def test_task_graph_in_sequence(run_poe):
    result = run_poe("ab", project="graphs")
    assert result.capture == (
        "Poe <= echo A1\n"
        "Poe <= echo A2\n"
        "Poe => 'a1: ' + ${a1} + ', a2: ' + ${a2}\n"
        "Poe => echo b\n"
    )
    assert result.stdout == ("a1: A1, a2: A2\nb\n")
    assert result.stderr == ""


def test_uses_private_var_filtered_from_subprocess(run_poe, is_windows):
    """Private vars introduced via uses stay private in downstream subprocess envs"""
    result = run_poe("uses_private_env", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo hidden\n"
        "Poe <= poe_test_echo VISIBLE\n"
        "Poe <= poe_test_echo visible\n"
        "Poe => poe_test_env\n"
    )
    stdout_lower = result.stdout.lower()
    if not is_windows:
        assert "_secret=hidden" not in result.stdout
    assert "_public=visible" in stdout_lower
    assert "normal=visible" in stdout_lower
    assert result.stderr == ""


def test_uses_private_var_accessible_in_template(run_poe):
    """Private vars introduced via uses are still available for template resolution"""
    result = run_poe("uses_private_template", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo hidden\n"
        "Poe <= poe_test_echo VISIBLE\n"
        "Poe <= poe_test_echo visible\n"
        "Poe => poe_test_echo hidden:VISIBLE:visible\n"
    )
    assert result.stdout == "hidden:VISIBLE:visible\n"
    assert result.stderr == ""


def test_uses_private_var_inherited_and_filtered(run_poe, is_windows):
    """Private vars introduced via uses stay private when inherited by subtasks"""
    result = run_poe("uses_private_inherited", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo hidden\n"
        "Poe <= poe_test_echo VISIBLE\n"
        "Poe <= poe_test_echo visible\n"
        "Poe => poe_test_env\n"
    )
    stdout_lower = result.stdout.lower()
    if not is_windows:
        assert "_secret=hidden" not in result.stdout
    assert "_public=visible" in stdout_lower
    assert "normal=visible" in stdout_lower
    assert result.stderr == ""


def test_uses_private_var_inherited_can_be_remapped_public(run_poe, is_windows):
    """A child task can alias inherited private uses vars to public env vars via env"""
    result = run_poe("uses_private_remapped", project="graphs")
    assert result.capture == ("Poe <= poe_test_echo hidden\n" "Poe => poe_test_env\n")
    stdout_lower = result.stdout.lower()
    if not is_windows:
        assert "_secret=hidden" not in result.stdout
    assert "public=hidden" in stdout_lower
    assert result.stderr == ""


def test_uses_env_imports_multiple_vars(run_poe, is_windows):
    """uses_env parses a task's stdout as an env file, importing several vars"""
    result = run_poe("uses_env_basic", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo_lines 'export AWS_KEY=abc123' "
        "AWS_SECRET=s3cr3t/xyz _token=hidden\n"
        "Poe => poe_test_env\n"
    )
    # The leading `export` is stripped and the slash in the value is preserved
    # (output is parsed as an env file, not whitespace-collapsed like uses)
    assert "AWS_KEY=abc123" in result.stdout
    assert "AWS_SECRET=s3cr3t/xyz" in result.stdout
    # The lowercase underscore-prefixed var stays private to the subprocess env
    if not is_windows:
        assert "_token=hidden" not in result.stdout
    assert result.stderr == ""


def test_uses_env_vars_available_in_template(run_poe):
    """Vars imported via uses_env are available for parameter expansion"""
    result = run_poe("uses_env_template", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo_lines 'export AWS_KEY=abc123' "
        "AWS_SECRET=s3cr3t/xyz _token=hidden\n"
        "Poe => poe_test_echo abc123:s3cr3t/xyz:hidden\n"
    )
    assert result.stdout == "abc123:s3cr3t/xyz:hidden\n"
    assert result.stderr == ""


def test_uses_env_multiple_tasks_later_wins(run_poe):
    """Multiple uses_env tasks merge in order; later entries override earlier ones"""
    result = run_poe("uses_env_multiple", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo_lines 'export AWS_KEY=abc123' "
        "AWS_SECRET=s3cr3t/xyz _token=hidden\n"
        "Poe <= poe_test_echo_lines AWS_KEY=overridden EXTRA=more\n"
        "Poe => poe_test_echo overridden:s3cr3t/xyz:more\n"
    )
    assert result.stdout == "overridden:s3cr3t/xyz:more\n"
    assert result.stderr == ""


def test_uses_overrides_uses_env_on_collision(run_poe):
    """An explicit uses entry takes precedence over a uses_env import of the same var"""
    result = run_poe("uses_env_uses_precedence", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo visible\n"
        "Poe <= poe_test_echo_lines 'export AWS_KEY=abc123' "
        "AWS_SECRET=s3cr3t/xyz _token=hidden\n"
        "Poe => poe_test_echo visible\n"
    )
    assert result.stdout == "visible\n"
    assert result.stderr == ""


def test_uses_env_empty_output_is_noop(run_poe):
    """A uses_env task that yields no assignments (comment only) runs cleanly"""
    result = run_poe("uses_env_empty", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo_lines '# just a comment'\n" "Poe => poe_test_echo done\n"
    )
    assert result.stdout == "done\n"
    assert result.stderr == ""


def test_uses_env_output_supports_parameter_expansion(run_poe):
    """
    ${VAR} in a uses_env task's output is expanded as an env file against the
    accumulating task env - here referencing a var from an earlier uses_env entry.
    """
    result = run_poe("uses_env_expansion", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo_lines BASE=hello\n"
        "Poe <= poe_test_echo_lines 'GREETING=${BASE}_world'\n"
        "Poe => poe_test_echo hello_world\n"
    )
    assert result.stdout == "hello_world\n"
    assert result.stderr == ""


def test_uses_env_unparseable_output_reports_clean_error(run_poe):
    """Output that isn't valid env file syntax yields a clear error, not a traceback"""
    result = run_poe("uses_env_unparseable", project="graphs")
    assert result.code == 1
    assert (
        "Could not parse the output of uses_env task '_unparseable_out' as an "
        "env file: Expected '=' after variable name 'this'"
    ) in result.capture
    assert result.stdout == ""


def test_uses_env_dry_run(run_poe):
    """In a dry run uses_env dependencies are reported as unresolved"""
    result = run_poe("-d", "uses_env_basic", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo_lines 'export AWS_KEY=abc123' "
        "AWS_SECRET=s3cr3t/xyz _token=hidden\n"
        "Poe ?? unresolved dependency task results via uses_env option for task"
        " 'uses_env_basic'\n"
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_uses_env_error_on_unknown_task(temp_pyproject, run_poe):
    project_path = temp_pyproject(
        """
        [tool.poe.tasks.consumer]
        cmd = "poe_test_echo hi"
        uses_env = "nope"
        """
    )
    result = run_poe("consumer", cwd=project_path)
    assert "Error: Invalid task 'consumer'" in result.capture
    assert (
        "'uses_env' option includes reference to unknown task: 'nope'"
    ) in result.capture
    assert result.stdout == ""


def test_uses_env_error_on_capture_stdout_task(temp_pyproject, run_poe):
    project_path = temp_pyproject(
        """
        [tool.poe.tasks._producer]
        cmd = "poe_test_echo hi"
        capture_stdout = "out.txt"

        [tool.poe.tasks.consumer]
        cmd = "poe_test_echo hi"
        uses_env = "_producer"
        """
    )
    result = run_poe("consumer", cwd=project_path)
    assert "Error: Invalid task 'consumer'" in result.capture
    assert (
        "'uses_env' option references task with 'capture_stdout' option set: "
        "'_producer'"
    ) in result.capture
    assert result.stdout == ""


def test_uses_env_error_on_use_exec_task(temp_pyproject, run_poe):
    project_path = temp_pyproject(
        """
        [tool.poe.tasks._producer]
        cmd = "poe_test_echo hi"
        use_exec = true

        [tool.poe.tasks.consumer]
        cmd = "poe_test_echo hi"
        uses_env = "_producer"
        """
    )
    result = run_poe("consumer", cwd=project_path)
    assert "Error: Invalid task 'consumer'" in result.capture
    assert (
        "'uses_env' option references task with 'use_exec' set to true: '_producer'"
    ) in result.capture
    assert result.stdout == ""
