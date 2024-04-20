import shutil

import pytest


def test_shell_task(run_poe_subproc):
    result = run_poe_subproc("count", project="shells")
    assert result.capture == (
        "Poe => poe_test_echo 1 && poe_test_echo 2 "
        "&& poe_test_echo $(python -c 'print(1 + 2)')\n"
    )
    assert result.stdout == "1\n2\n3\n"
    assert result.stderr == ""


def test_shell_task_raises_given_extra_args(run_poe):
    result = run_poe("count", "bla", project="shells")
    assert "\n\nError: Shell task 'count' does not accept arguments" in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_multiline_non_default_type_task(run_poe_subproc):
    # This should be exactly the same as calling the echo task directly
    result = run_poe_subproc("sing", project="shells")
    assert result.capture == (
        'Poe => poe_test_echo "this is the story";\n'
        'poe_test_echo "all about how" &&      # the last line won\'t run\n'
        'poe_test_echo "my life got flipped;\n'
        '  turned upside down" ||\npoe_test_echo "bam bam baaam bam"\n'
    )
    assert result.stdout == (
        "this is the story\n"
        "all about how\n"
        "my life got flipped;\n"
        "  turned upside down\n"
    )
    assert result.stderr == ""


def test_shell_task_with_dash_case_arg(run_poe_subproc):
    result = run_poe_subproc(
        "greet", "--formal-greeting=hey", "--subject=you", project="shells"
    )
    assert result.capture == ("Poe => poe_test_echo $formal_greeting $subject\n")
    assert result.stdout == "hey you\n"
    assert result.stderr == ""


@pytest.mark.skipif(not shutil.which("sh"), reason="No sh available")
def test_interpreter_sh(run_poe_subproc):
    result = run_poe_subproc("echo_sh", project="shells")
    assert result.capture == ("Poe => poe_test_echo $0 $test_var\n")
    assert "roflcopter" in result.stdout
    assert result.stderr == ""


@pytest.mark.skipif(not shutil.which("bash"), reason="No bash available")
def test_interpreter_bash(run_poe_subproc):
    result = run_poe_subproc("echo_bash", project="shells")
    assert result.capture == ("Poe => poe_test_echo $0 $test_var\n")
    assert "bash" in result.stdout
    assert "roflcopter" in result.stdout
    assert result.stderr == ""


@pytest.mark.skipif(not shutil.which("pwsh"), reason="No pwsh available")
def test_interpreter_pwsh(run_poe_subproc):
    result = run_poe_subproc("echo_pwsh", project="shells")
    assert result.capture == ("Poe => poe_test_echo $ENV:test_var\n")
    assert "roflcopter" in result.stdout
    assert result.stderr == ""


@pytest.mark.skipif(not shutil.which("powershell"), reason="No powershell available")
def test_interpreter_powershell(run_poe_subproc):
    result = run_poe_subproc("echo_powershell", project="shells")
    assert result.capture == ("Poe => poe_test_echo $ENV:test_var\n")
    assert "roflcopter" in result.stdout
    assert result.stderr == ""


def test_interpreter_python(run_poe_subproc):
    result = run_poe_subproc("echo_python", project="shells")
    assert result.capture == (
        "Poe => import sys, os\n\ndef run():\n"
        '    print(sys.version_info, os.environ.get("test_var"))\n\nrun()\n'
    )
    assert result.stdout.startswith("sys.version_info(major=3,")
    assert "roflcopter" in result.stdout
    assert result.stderr == ""


def test_bad_interpreter_config(run_poe_subproc, projects):
    result = run_poe_subproc(
        f'-C={projects["shells/bad_interpreter"]}',
        "bad-interpreter",
    )
    assert (
        "Error: Invalid task 'bad-interpreter'\n"
        "     | Invalid value for option 'interpreter',\n"
        "     | Expected one of "
        "('posix', 'sh', 'bash', 'zsh', 'fish', 'pwsh', 'powershell', 'python')\n"
    ) in result.capture
    assert result.stdout == ""
    assert result.stderr == ""


def test_global_interpreter_config(run_poe_subproc, projects):
    result = run_poe_subproc(
        f'-C={projects["shells/shell_interpreter_config"]}',
        "echo_python",
    )
    assert result.capture == "Poe => import sys\nprint(sys.version_info)\n"
    assert result.stdout.startswith("sys.version_info(major=3,")
    assert result.stderr == ""


def test_shell_task_with_multiple_value_arg(run_poe_subproc):
    result = run_poe_subproc(
        "multiple-value-arg", "hey", "1", "2", "3", project="shells"
    )
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
