import pytest


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
    assert result.capture == ("Poe <= poe_test_echo hidden\nPoe => poe_test_env\n")
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


def test_uses_env_from_switch_task(run_poe):
    """
    A switch task's selected-case output is preserved as raw multiline text, so
    uses_env can parse every variable it emits rather than collapsing them onto
    a single line (which would fold all but the first var into one value).
    """
    result = run_poe("uses_env_from_switch", project="graphs")
    assert result.stdout == "abc:xyz\n"
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
        "Poe <= poe_test_echo_lines '# just a comment'\nPoe => poe_test_echo done\n"
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


def test_uses_env_passes_args_with_parameter_expansion(run_poe):
    """
    A uses_env invocation accepts arguments and parameter expansion: the host's
    own arg is expanded into the invocation and passed on to the producer task.
    """
    result = run_poe("uses_env_with_args", "--profile", "prod", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo_lines TOKEN=prod-secret\n"
        "Poe => poe_test_echo prod-secret\n"
    )
    assert result.stdout == "prod-secret\n"
    assert result.stderr == ""


def test_uses_env_args_fall_back_to_defaults(run_poe):
    """When the host arg is unset, the producer's arg default applies"""
    result = run_poe("uses_env_with_args", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo_lines TOKEN=dev-secret\nPoe => poe_test_echo dev-secret\n"
    )
    assert result.stdout == "dev-secret\n"
    assert result.stderr == ""


def test_uses_env_vars_available_to_task_env(run_poe):
    """
    uses_env vars are applied before the task's own env, so an env entry can
    reference (and extend) a variable provided via uses_env.
    """
    result = run_poe("uses_env_referenced_in_task_env", project="graphs")
    assert result.capture == (
        "Poe <= poe_test_echo_lines _secret=s3kr3t\n"
        "Poe => poe_test_echo prefix-s3kr3t\n"
    )
    assert result.stdout == "prefix-s3kr3t\n"
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
    project_path = temp_pyproject("""
        [tool.poe.tasks.consumer]
        cmd = "poe_test_echo hi"
        uses_env = "nope"
        """)
    result = run_poe("consumer", cwd=project_path)
    assert "Error: Invalid task 'consumer'" in result.capture
    assert (
        "'uses_env' option includes reference to unknown task: 'nope'"
    ) in result.capture
    assert result.stdout == ""


def test_uses_env_error_on_capture_stdout_task(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks._producer]
        cmd = "poe_test_echo hi"
        capture_stdout = "out.txt"

        [tool.poe.tasks.consumer]
        cmd = "poe_test_echo hi"
        uses_env = "_producer"
        """)
    result = run_poe("consumer", cwd=project_path)
    assert "Error: Invalid task 'consumer'" in result.capture
    assert (
        "'uses_env' option references task with 'capture_stdout' option set: "
        "'_producer'"
    ) in result.capture
    assert result.stdout == ""


def test_uses_env_error_on_use_exec_task(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks._producer]
        cmd = "poe_test_echo hi"
        use_exec = true

        [tool.poe.tasks.consumer]
        cmd = "poe_test_echo hi"
        uses_env = "_producer"
        """)
    result = run_poe("consumer", cwd=project_path)
    assert "Error: Invalid task 'consumer'" in result.capture
    assert (
        "'uses_env' option references task with 'use_exec' set to true: '_producer'"
    ) in result.capture
    assert result.stdout == ""


def test_uses_env_also_a_dep(run_poe):
    """
    A task referenced by both deps and uses_env is captured for the uses_env
    consumer even though the deps reference alone would leave it uncaptured.
    """
    result = run_poe("uses_env_also_a_dep", project="graphs")
    assert result.stderr == ""
    # The uses_env import resolves (SECRET is set), rather than raising
    assert "Got: s3cr3t" in result.stdout


def test_uses_error_on_sequence_task(temp_pyproject, run_poe):
    """
    Referencing a sequence task via uses is rejected with a curated config
    error at validation time, not an unhandled AssertionError at runtime.
    """
    project_path = temp_pyproject("""
        [tool.poe.tasks._seq]
        sequence = [{ cmd = "poe_test_echo A" }, { cmd = "poe_test_echo B" }]

        [tool.poe.tasks.consumer]
        cmd = "poe_test_echo hi"
        uses = { X = "_seq" }
        """)
    result = run_poe("consumer", cwd=project_path)
    assert "Error: Invalid task 'consumer'" in result.capture
    assert (
        "'uses' option references task that does not support output capture: '_seq'"
    ) in result.capture
    assert result.stdout == ""


def test_uses_env_error_on_sequence_task(temp_pyproject, run_poe):
    """
    Referencing a sequence task via uses_env is rejected with a curated config
    error at validation time, not an unhandled AssertionError at runtime.
    """
    project_path = temp_pyproject("""
        [tool.poe.tasks._seq]
        sequence = [{ cmd = "poe_test_echo A" }, { cmd = "poe_test_echo B" }]

        [tool.poe.tasks.consumer]
        cmd = "poe_test_echo hi"
        uses_env = "_seq"
        """)
    result = run_poe("consumer", cwd=project_path)
    assert "Error: Invalid task 'consumer'" in result.capture
    assert (
        "'uses_env' option references task that does not support output capture: '_seq'"
    ) in result.capture
    assert result.stdout == ""


def test_uses_env_error_on_parallel_task(temp_pyproject, run_poe):
    """
    Referencing a parallel task via uses_env is likewise rejected with a curated
    config error rather than an unhandled AssertionError.
    """
    project_path = temp_pyproject("""
        [tool.poe.tasks._par]
        parallel = [{ cmd = "poe_test_echo A" }, { cmd = "poe_test_echo B" }]

        [tool.poe.tasks.consumer]
        cmd = "poe_test_echo hi"
        uses_env = "_par"
        """)
    result = run_poe("consumer", cwd=project_path)
    assert "Error: Invalid task 'consumer'" in result.capture
    assert (
        "'uses_env' option references task that does not support output capture: '_par'"
    ) in result.capture
    assert result.stdout == ""


def test_uses_env_via_ref_to_sequence_rejected(temp_pyproject, run_poe):
    """
    A ref forwards capture to its target, so uses_env referencing a ref that
    points at a sequence is rejected at config time via the recursive
    accepts_option check (rather than tracebacking at runtime).
    """
    project_path = temp_pyproject("""
        [tool.poe.tasks._seq]
        sequence = [{ cmd = "poe_test_echo A" }, { cmd = "poe_test_echo B" }]

        [tool.poe.tasks._myref]
        ref = "_seq"

        [tool.poe.tasks.consumer]
        cmd = "poe_test_echo hi"
        uses_env = "_myref"
        """)
    result = run_poe("consumer", cwd=project_path)
    assert "Error: Invalid task 'consumer'" in result.capture
    assert (
        "'uses_env' option references task that does not support output capture:"
        " '_myref'"
    ) in result.capture
    assert result.stdout == ""


def test_uses_env_via_switch_with_sequence_case_rejected(temp_pyproject, run_poe):
    """
    A switch forwards capture to the selected case, so uses_env referencing a
    switch with a non-capturable (sequence) case is rejected at config time.
    """
    project_path = temp_pyproject("""
        [tool.poe.tasks.consumer]
        cmd = "poe_test_echo hi"
        uses_env = "_sw"

        [tool.poe.tasks._sw]
        control.expr = "1"

          [[tool.poe.tasks._sw.switch]]
          case = "1"
          sequence = [{ cmd = "poe_test_echo A" }]
        """)
    result = run_poe("consumer", cwd=project_path)
    assert "Error: Invalid task 'consumer'" in result.capture
    assert (
        "'uses_env' option references task that does not support output capture: '_sw'"
    ) in result.capture
    assert result.stdout == ""


@pytest.mark.parametrize(
    ("tasks_config", "expected_cycle"),
    [
        (
            """
            [tool.poe.tasks.a]
            cmd = "poe_test_echo a"
            deps = ["b"]

            [tool.poe.tasks.b]
            cmd = "poe_test_echo b"
            deps = ["a"]
            """,
            "a -> b -> a",
        ),
        (
            """
            [tool.poe.tasks.a]
            cmd = "poe_test_echo a"
            deps = ["a"]
            """,
            "a -> a",
        ),
        (
            """
            [tool.poe.tasks.a]
            cmd = "poe_test_echo a"
            uses = { B = "b" }

            [tool.poe.tasks.b]
            cmd = "poe_test_echo b"
            deps = ["c --flag"]

            [tool.poe.tasks.c]
            cmd = "poe_test_echo c"
            deps = ["a"]
            args = [{ name = "flag", type = "boolean" }]
            """,
            "a -> b -> c -> a",
        ),
        (
            # Each repetition has a different invocation, so this recursed without
            # limit when cycles were detected by invocation rather than task name
            """
            [tool.poe.tasks.a]
            cmd = "poe_test_echo a"
            deps = ["a --level ${level}x"]
            args = [{ name = "level", default = "x" }]
            """,
            "a -> a",
        ),
    ],
    ids=["two_tasks", "self_dependency", "via_uses_and_args", "changing_args"],
)
def test_cyclic_deps_are_rejected(
    temp_pyproject, run_poe, tasks_config, expected_cycle
):
    project_path = temp_pyproject(tasks_config)
    result = run_poe("a", cwd=project_path)
    assert result.code == 1
    assert (f"Cyclic task reference detected: {expected_cycle}\n") in result.capture
    assert result.stdout == ""


def test_cyclic_deps_error_excludes_tasks_leading_into_the_cycle(
    temp_pyproject, run_poe
):
    project_path = temp_pyproject("""
        [tool.poe.tasks.start]
        cmd = "poe_test_echo start"
        deps = ["a"]

        [tool.poe.tasks.a]
        cmd = "poe_test_echo a"
        deps = ["b"]

        [tool.poe.tasks.b]
        cmd = "poe_test_echo b"
        deps = ["c"]

        [tool.poe.tasks.c]
        cmd = "poe_test_echo c"
        deps = ["a"]
        """)
    result = run_poe("start", cwd=project_path)
    assert result.code == 1
    assert "Cyclic task reference detected: a -> b -> c -> a\n" in (result.capture)
    assert result.stdout == ""


def test_shared_dep_is_not_a_cycle(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.a]
        cmd = "poe_test_echo a"
        deps = ["b", "c"]

        [tool.poe.tasks.b]
        cmd = "poe_test_echo b"
        deps = ["d"]

        [tool.poe.tasks.c]
        cmd = "poe_test_echo c"
        deps = ["d"]

        [tool.poe.tasks.d]
        cmd = "poe_test_echo d"
        """)
    result = run_poe("a", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "d\nb\nc\na\n"


def test_task_reused_with_different_args_is_not_a_cycle(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.say]
        cmd = "poe_test_echo ${word}"
        args = [{ name = "word", positional = true }]

        [tool.poe.tasks.left]
        cmd = "poe_test_echo left"
        deps = ["say one", "say two"]

        [tool.poe.tasks.right]
        cmd = "poe_test_echo right"
        deps = ["say one", "say three"]

        [tool.poe.tasks.top]
        cmd = "poe_test_echo top"
        deps = ["left", "right"]
        """)
    result = run_poe("top", cwd=project_path)
    assert result.code == 0, result.capture
    assert sorted(result.stdout.splitlines()) == sorted(
        ["one", "two", "three", "left", "right", "top"]
    )
    assert result.stdout.endswith("top\n")


GRAPH_WITH_CAPTURED_AND_UNCAPTURED_NON_SOURCE = """
    [tool.poe.tasks.pre]
    cmd = "poe_test_echo PRE"

    [tool.poe.tasks.val]
    cmd = "poe_test_echo VAL"
    deps = ["pre"]

    [tool.poe.tasks.sink]
    cmd = "poe_test_echo X=${X}"
    deps = ["val"]
    uses = { X = "val" }

    [tool.poe.tasks.mid]
    cmd = "poe_test_echo MID Y=${Y}"
    uses = { Y = "val" }

    [tool.poe.tasks.sink3]
    cmd = "poe_test_echo SINK3"
    deps = ["val", "mid"]

    [tool.poe.tasks.ref_sink3]
    ref = "sink3"
    """


@pytest.mark.parametrize(
    ("task", "expected_stdout"),
    [
        ("sink", "PRE\nVAL\nX=VAL\n"),
        ("sink3", "PRE\nVAL\nMID Y=VAL\nSINK3\n"),
        ("ref_sink3", "PRE\nVAL\nMID Y=VAL\nSINK3\n"),
    ],
)
def test_task_with_deps_both_captured_and_uncaptured(
    temp_pyproject, run_poe, task, expected_stdout
):
    """
    A task that has deps of its own, and is both a plain dep and a uses source, runs
    once uncaptured and once captured, and all of its dependants run after it
    """
    project_path = temp_pyproject(GRAPH_WITH_CAPTURED_AND_UNCAPTURED_NON_SOURCE)
    result = run_poe(task, cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == expected_stdout
    assert "Poe <= poe_test_echo VAL\n" in result.capture
    assert "Poe => poe_test_echo VAL\n" in result.capture


@pytest.mark.parametrize(
    ("tasks_config", "expected_error"),
    [
        (
            """
            [tool.poe.tasks.a]
            ref = "a"
            """,
            "a -> a",
        ),
        (
            """
            [tool.poe.tasks.a]
            ref = "b --flag"

            [tool.poe.tasks.b]
            ref = "a"
            """,
            "a -> b -> a",
        ),
        (
            """
            [tool.poe.tasks.a]
            sequence = ["echo_x", "a"]

            [tool.poe.tasks.echo_x]
            cmd = "poe_test_echo x"
            """,
            "a -> a",
        ),
        (
            """
            [tool.poe.tasks.a]
            sequence = [{ cmd = "poe_test_echo x" }, [{ ref = "b" }]]

            [tool.poe.tasks.b]
            parallel = ["a"]
            """,
            "a -> b -> a",
        ),
        (
            """
            [tool.poe.tasks.a]
            cmd = "poe_test_echo a"
            deps = ["b"]

            [tool.poe.tasks.b]
            ref = "a"
            """,
            "a -> b -> a",
        ),
        (
            """
            [tool.poe.tasks.a]
            cmd = "poe_test_echo ${X}"
            uses = { X = "b" }

            [tool.poe.tasks.b]
            ref = "a"
            """,
            "a -> b -> a",
        ),
    ],
    ids=[
        "ref_self",
        "ref_pair",
        "sequence_self",
        "inline_ref_via_parallel",
        "deps_via_ref",
        "uses_via_ref",
    ],
)
def test_cyclic_task_references_are_rejected(
    temp_pyproject, run_poe, tasks_config, expected_error
):
    """
    Cycles through ref, sequence, and parallel tasks, alone or mixed with deps and
    uses, are rejected at config validation. Poe is run without a task so that a
    regression can't recurse without limit.
    """
    project_path = temp_pyproject(tasks_config)
    result = run_poe(cwd=project_path)
    assert result.code == 1
    assert "Error: Invalid task 'a'\n" in result.capture
    assert f"Cyclic task reference detected: {expected_error}\n" in result.capture


def test_recursion_via_switch_case_is_not_a_cycle(temp_pyproject, run_poe):
    """
    A switch case is run conditionally, so it may be used to recurse until the
    control task selects another case
    """
    project_path = temp_pyproject("""
        [tool.poe.tasks.countdown]
        control.expr = "int(${n}) > 0"
        args = [{ name = "n", default = "2" }]

        [[tool.poe.tasks.countdown.switch]]
        case = "True"
        ref = "_countdown_step --n ${n}"

        [[tool.poe.tasks.countdown.switch]]
        cmd = "poe_test_echo done"

        [tool.poe.tasks._countdown_step]
        ref = "countdown --n ${next}"
        args = ["n"]
        uses = { next = "_decrement --n ${n}" }

        [tool.poe.tasks._decrement]
        expr = "int(${n}) - 1"
        args = ["n"]
        """)
    result = run_poe("countdown", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "done\n"
    assert "Poe <= int(${n}) - 1\n" in result.capture
