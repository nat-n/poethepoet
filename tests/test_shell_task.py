import re
import shutil

import pytest


def _strip_terminal_control_sequences(text: str) -> str:
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)


def _clean_shell_output(text: str) -> str:
    return _strip_terminal_control_sequences(text).strip()


def test_shell_task(run_poe):
    result = run_poe("count", project="shells")
    assert result.capture == (
        "Poe => poe_test_echo 1 && poe_test_echo 2 "
        "&& poe_test_echo $(python -c 'print(1 + 2)')\n"
    )
    assert result.stdout == "1\n2\n3\n"
    assert result.stderr == ""


def test_shell_task_given_extra_args(run_poe):
    """Extra args passed to a shell task without $POE_EXTRA_ARGS are silently ignored"""
    result = run_poe("count", "bla", project="shells")
    assert result.capture == (
        "Poe => poe_test_echo 1 && poe_test_echo 2 "
        "&& poe_test_echo $(python -c 'print(1 + 2)')\n"
    )
    assert result.stdout == "1\n2\n3\n"
    assert result.stderr == ""


def test_multiline_non_default_type_task(run_poe):
    # This should be exactly the same as calling the echo task directly
    result = run_poe("sing", project="shells")
    assert result.capture == (
        'Poe => poe_test_echo "this is the story";\n'
        'poe_test_echo "all about how" &&      # the last line won\'t run\n'
        'poe_test_echo "my life got flipped;\n'
        '  turned upside down" ||\npoe_test_echo "bam bam baaam bam"\n'
    )
    assert result.stdout == (
        "this is the story\nall about how\nmy life got flipped;\n  turned upside down\n"
    )
    assert result.stderr == ""


def test_shell_task_with_dash_case_arg(run_poe):
    result = run_poe(
        "greet", "--formal-greeting=hey", "--subject=you", project="shells"
    )
    assert result.capture == ("Poe => poe_test_echo $formal_greeting $subject\n")
    assert result.stdout == "hey you\n"
    assert result.stderr == ""


@pytest.mark.skipif(not shutil.which("sh"), reason="No sh available")
def test_interpreter_sh(run_poe):
    result = run_poe("echo_sh", project="shells")
    assert result.capture == ("Poe => poe_test_echo $0 $test_var\n")
    assert "roflcopter" in result.stdout
    assert result.stderr == ""


@pytest.mark.skipif(not shutil.which("bash"), reason="No bash available")
def test_interpreter_bash(run_poe):
    result = run_poe("echo_bash", project="shells")
    assert result.capture == ("Poe => poe_test_echo $0 $test_var\n")
    assert "bash" in result.stdout
    assert "roflcopter" in result.stdout
    assert result.stderr == ""


@pytest.mark.skipif(not shutil.which("pwsh"), reason="No pwsh available")
def test_interpreter_pwsh(run_poe):
    result = run_poe("echo_pwsh", project="shells")
    assert result.capture == ("Poe => poe_test_echo $ENV:test_var\n")
    assert "roflcopter" in result.stdout
    assert result.stderr == ""


@pytest.mark.skipif(not shutil.which("powershell"), reason="No powershell available")
def test_interpreter_powershell(run_poe):
    result = run_poe("echo_powershell", project="shells")
    assert result.capture == ("Poe => poe_test_echo $ENV:test_var\n")
    assert "roflcopter" in result.stdout
    assert result.stderr == ""


def test_interpreter_python(run_poe):
    result = run_poe("echo_python", project="shells")
    assert result.capture == (
        "Poe => import sys, os\n\ndef run():\n"
        '    print(sys.version_info, os.environ.get("test_var"))\n\nrun()\n'
    )
    assert result.stdout.startswith("sys.version_info(major=3,")
    assert "roflcopter" in result.stdout
    assert result.stderr == ""


def test_bad_interpreter_config(run_poe, projects):
    result = run_poe(
        f"-C={projects['shells/bad_interpreter']}",
        "bad-interpreter",
    )
    assert "Error: Invalid task 'bad-interpreter'" in result.capture
    assert "Option 'interpreter' must have a value of type:" in result.capture
    for valid_value in (
        "'posix'",
        "'sh'",
        "'bash'",
        "'zsh'",
        "'fish'",
        "'pwsh'",
        "'powershell'",
        "'python'",
    ):
        assert valid_value in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_global_interpreter_config(run_poe, projects):
    result = run_poe(
        f"-C={projects['shells/shell_interpreter_config']}",
        "echo_python",
    )
    assert result.capture == "Poe => import sys\nprint(sys.version_info)\n"
    assert result.stdout.startswith("sys.version_info(major=3,")
    assert result.stderr == ""


def test_shell_task_with_multiple_value_arg(run_poe):
    result = run_poe("multiple-value-arg", "hey", "1", "2", "3", project="shells")
    assert (
        result.capture
        == """Poe => poe_test_echo "first: ${first} second: ${second}"

# bash treats space delimited string like array for iteration!
for word in $second; do
  poe_test_echo $word
done
"""
    )
    assert result.stdout == "first: hey second: 1 2 3\n1\n2\n3\n"
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("cli_args", "expected_env_lines"),
    [
        pytest.param(
            (),
            """${non}= ${non:+plus}= ${non:-minus}=minus
${fal}= ${fal:+plus}= ${fal:-minus}=minus
${tru}=True ${tru:+plus}=plus ${tru:-minus}=True
${txt}=True ${txt:+plus}=plus ${txt:-minus}=True
""",
            id="defaults",
        ),
        pytest.param(
            ("--non", "--tru", "--fal", "--txt"),
            """${non}=True ${non:+plus}=plus ${non:-minus}=True
${fal}=True ${fal:+plus}=plus ${fal:-minus}=True
${tru}= ${tru:+plus}= ${tru:-minus}=minus
${txt}= ${txt:+plus}= ${txt:-minus}=minus
""",
            id="all_toggled",
        ),
        pytest.param(
            ("--tru",),
            """${non}= ${non:+plus}= ${non:-minus}=minus
${fal}= ${fal:+plus}= ${fal:-minus}=minus
${tru}= ${tru:+plus}= ${tru:-minus}=minus
${txt}=True ${txt:+plus}=plus ${txt:-minus}=True
""",
            id="negate_tru",
        ),
    ],
)
def test_shell_boolean_flag(
    run_poe, cli_args: tuple[str, ...], expected_env_lines: str
) -> None:
    """
    Same invariant as the cmd suite, exercised against a shell task.
    Boolean args toggle to/from the truthy bool default; the resolved bool
    propagates to env vars as ``"True"`` (truthy) or unset (falsy).
    """
    result = run_poe("booleans", *cli_args, project="shells")
    assert result.stdout.endswith(expected_env_lines)


def test_shell_bool_env_collision_flag_set(run_poe):
    result = run_poe("bool_env_collision", "--MY_FLAG", project="shells")
    assert result.stdout.strip() == "True"


def test_shell_bool_env_collision_flag_unset(run_poe):
    result = run_poe("bool_env_collision", project="shells")
    assert result.stdout.strip() == "fallback"


def test_shell_bool_env_presence_true(run_poe):
    result = run_poe("bool_env_presence", project="shells")
    assert result.stdout.strip() == "True 'True'"


def test_shell_bool_env_presence_false_is_unset(run_poe):
    result = run_poe("bool_env_presence", "--MY_FLAG", project="shells")
    assert result.stdout.strip() == "False None"


@pytest.mark.skipif(not shutil.which("sh"), reason="No sh available")
def test_shell_unset_semantics_sh_true(run_poe):
    result = run_poe("bool_unset_semantics_sh", project="shells")
    assert result.stdout.strip() == "set:True:True"


@pytest.mark.skipif(not shutil.which("sh"), reason="No sh available")
def test_shell_unset_semantics_sh_false(run_poe):
    result = run_poe("bool_unset_semantics_sh", "--MY_FLAG", project="shells")
    assert result.stdout.strip() == ":unset:fallback"


@pytest.mark.skipif(not shutil.which("pwsh"), reason="No pwsh available")
def test_shell_unset_semantics_pwsh_true(run_poe):
    result = run_poe("bool_unset_semantics_pwsh", project="shells")
    assert _clean_shell_output(result.stdout) == "True|True|True"


@pytest.mark.skipif(not shutil.which("pwsh"), reason="No pwsh available")
def test_shell_unset_semantics_pwsh_false(run_poe):
    result = run_poe("bool_unset_semantics_pwsh", "--MY_FLAG", project="shells")
    assert _clean_shell_output(result.stdout) == "False|unset|fallback"


def test_shell_task_extra_args_via_poe_extra_args(run_poe):
    """Free args passed after -- are available in shell scripts via $POE_EXTRA_ARGS"""
    result = run_poe("echo-extra-args", "--", "foo", "bar", project="shells")
    assert result.capture == "Poe => poe_test_echo $target $POE_EXTRA_ARGS\n"
    assert result.stdout == "default foo bar\n"
    assert result.stderr == ""


def test_shell_task_extra_args_via_poe_extra_args_without_named_args(run_poe):
    """Shell task with $POE_EXTRA_ARGS but no named args accepts free args directly"""
    result = run_poe("echo-extra-args-no-named", "foo", "bar", project="shells")
    assert result.capture == "Poe => poe_test_echo $POE_EXTRA_ARGS\n"
    assert result.stdout == "foo bar\n"
    assert result.stderr == ""
