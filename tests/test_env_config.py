import shutil
import sys
from pathlib import Path

import pytest

EXAMPLE_CONFIG = """
[tool.poe.env]
GLOBAL_POE_ROOT = "${POE_ROOT}"
GLOBAL_POE_PWD = "${POE_PWD}"

[tool.poe.tasks.my-task]
default_item_type = "cmd"
sequence = [
  "echo POE_ROOT: ${POE_ROOT}",
  "echo GLOBAL_POE_ROOT: ${GLOBAL_POE_ROOT}",
  "echo TASK_POE_ROOT: ${TASK_POE_ROOT}",
  "echo POE_PWD: ${POE_PWD}",
  "echo GLOBAL_POE_PWD: ${GLOBAL_POE_PWD}",
  "echo TASK_POE_PWD: ${TASK_POE_PWD}",
]

[tool.poe.tasks.my-task.env]
TASK_POE_ROOT = "${POE_ROOT}"
TASK_POE_PWD = "${POE_PWD}"
"""


def test_global_env_templating(temp_pyproject, run_poe):
    project_path = temp_pyproject(EXAMPLE_CONFIG)
    result = run_poe("my-task", cwd=project_path)
    assert result.code == 0

    printed_vars = {
        line.split(": ")[0]: line.split(": ")[1]
        for line in result.stdout.split("\n")
        if ": " in line
    }
    for value in printed_vars.values():
        assert value.endswith(str(project_path)[5:])


EXAMPLE_WITH_ENV_COMPOSITION = """
[tool.poe.env]
BASE_DIR = "/foo"
SUBDIR = "${BASE_DIR}/bar"
FILE = "${SUBDIR}/baz"

[tool.poe.tasks.frobnicate]
expr = "${FILE}"
"""


def test_substitution_in_envvar(temp_pyproject, run_poe):
    project_path = temp_pyproject(EXAMPLE_WITH_ENV_COMPOSITION)
    result = run_poe("frobnicate", cwd=project_path)

    assert result.capture == "Poe => ${FILE}\n"
    assert result.stdout == "/foo/bar/baz\n"
    assert result.stderr == ""


# ---------------------------------------------------------------------------
# Parameter expansion operators (:- and :+) in env config
# ---------------------------------------------------------------------------


def test_default_value_in_global_env(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.env]
        GREETING = "${NAME:-world}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${GREETING}"
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "world\n"
    assert result.stderr == ""


def test_default_value_overridden_in_global_env(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.env]
        GREETING = "${NAME:-world}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${GREETING}"
        """)
    result = run_poe("show", cwd=project_path, env={"NAME": "alice"})
    assert result.code == 0
    assert result.stdout == "alice\n"
    assert result.stderr == ""


def test_default_value_with_empty_env_var(temp_pyproject, run_poe):
    """
    An env var set to empty string is treated as unset for :- purposes.
    """
    project_path = temp_pyproject("""
        [tool.poe.env]
        GREETING = "${NAME:-world}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${GREETING}"
        """)
    result = run_poe("show", cwd=project_path, env={"NAME": ""})
    assert result.code == 0
    assert result.stdout == "world\n"
    assert result.stderr == ""


def test_alternate_value_in_global_env(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.env]
        FLAG_DISPLAY = "${VERBOSE:+--verbose}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo flag=${FLAG_DISPLAY}"
        """)
    result = run_poe("show", cwd=project_path, env={"VERBOSE": "1"})
    assert result.code == 0
    assert result.stdout == "flag=--verbose\n"
    assert result.stderr == ""


def test_alternate_value_unset_in_global_env(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.env]
        FLAG_DISPLAY = "${VERBOSE:+--verbose}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo flag=${FLAG_DISPLAY}"
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "flag=\n"
    assert result.stderr == ""


def test_default_value_in_task_env(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${GREETING}"

        [tool.poe.tasks.show.env]
        GREETING = "${NAME:-stranger}"
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "stranger\n"
    assert result.stderr == ""


def test_env_composition_with_default(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.env]
        SCHEME = "${PROTOCOL:-https}"
        BASE_URL = "${SCHEME}://${HOST:-localhost}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${BASE_URL}"
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "https://localhost\n"
    assert result.stderr == ""


def test_default_value_in_arg_default(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${greeting}"
        args = [{ name = "greeting", default = "${SALUTATION:-hello}" }]
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "hello\n"
    assert result.stderr == ""


def test_default_value_in_arg_default_overridden(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${greeting}"
        args = [{ name = "greeting", default = "${SALUTATION:-hello}" }]
        """)
    result = run_poe("show", cwd=project_path, env={"SALUTATION": "howdy"})
    assert result.code == 0
    assert result.stdout == "howdy\n"
    assert result.stderr == ""


def test_default_value_in_sequence_item_env(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.show]
        sequence = [
          { cmd = "poe_test_echo ${LABEL}", env = { LABEL = "${TAG:-latest}" } },
        ]
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "latest\n"
    assert result.stderr == ""


def test_default_value_in_capture_stdout(temp_pyproject, run_poe, tmp_path):
    """
    ${VAR:-default} in a capture_stdout path.
    """
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    project_path = temp_pyproject(f"""
        [tool.poe.tasks.show]
        cmd = "echo captured"
        capture_stdout = "{output_dir.as_posix()}/${{OUTFILE:-result.txt}}"
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stderr == ""
    assert (output_dir / "result.txt").read_text().strip() == "captured"


# ---------------------------------------------------------------------------
# Invalid template syntax gives a helpful error rather than a traceback
# ---------------------------------------------------------------------------

bad_template_examples = [
    (
        "task env",
        """
        [tool.poe.tasks.show]
        cmd = "poe_test_echo hi"
        env = { X = "${U-x}" }
        """,
        "Invalid template '${U-x}'",
        "Illegal character in parameter name '-'",
    ),
    (
        "task cwd",
        """
        [tool.poe.tasks.show]
        cmd = "poe_test_echo hi"
        cwd = "${HOME"
        """,
        "Invalid template '${HOME'",
        "expected closing '}' after '${'",
    ),
    (
        "task envfile",
        """
        [tool.poe.tasks.show]
        cmd = "poe_test_echo hi"
        envfile = "${}"
        """,
        "Invalid template '${}'",
        "Bad substitution: ${}",
    ),
    (
        "capture_stdout",
        """
        [tool.poe.tasks.show]
        cmd = "poe_test_echo hi"
        capture_stdout = "${X:=y}"
        """,
        "Invalid template '${X:=y}'",
        "Unsupported operator ':='",
    ),
    (
        "global env",
        """
        [tool.poe]
        env = { X = "${U:?message}" }

        [tool.poe.tasks.show]
        cmd = "poe_test_echo hi"
        """,
        "Invalid template '${U:?message}'",
        "Unsupported operator ':?'",
    ),
    (
        "global envfile",
        """
        [tool.poe]
        envfile = "${.env"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo hi"
        """,
        "Invalid template '${.env'",
        "Illegal first character in parameter name '.'",
    ),
]


@pytest.mark.parametrize(
    ("config", "expected_error", "expected_detail"),
    [example[1:] for example in bad_template_examples],
    ids=[example[0] for example in bad_template_examples],
)
def test_bad_template_syntax_is_reported(
    temp_pyproject, run_poe, config, expected_error, expected_detail
):
    project_path = temp_pyproject(config)
    result = run_poe("show", cwd=project_path)
    assert result.code == 1
    assert expected_error in result.capture
    assert expected_detail in result.capture
    assert "Traceback" not in result.capture
    assert result.stdout == ""


VENV_BIN_DIR = str(Path(sys.executable).parent)


@pytest.mark.skipif(
    shutil.which("git", path=VENV_BIN_DIR) is not None,
    reason="git is installed alongside the python executable",
)
def test_git_vars_without_git_executable(temp_pyproject, run_poe):
    """
    If the git executable isn't available then POE_GIT_DIR and POE_GIT_ROOT resolve
    to empty values, just as when the project isn't inside a git repo.
    """
    project_path = temp_pyproject("""
        [tool.poe.tasks.show]
        cmd = "poe_test_echo dir=${GIT_DIR_VAL}. root=${GIT_ROOT_VAL}."
        env = { GIT_DIR_VAL = "${POE_GIT_DIR}", GIT_ROOT_VAL = "${POE_GIT_ROOT}" }
        """)
    result = run_poe("show", cwd=project_path, env={"PATH": VENV_BIN_DIR})
    assert result.code == 0
    assert result.stdout == "dir=. root=.\n"
    assert result.stderr == ""


def test_poe_extra_args_not_inherited_from_host_env(run_poe):
    """
    POE_EXTRA_ARGS in the host environment (e.g. set by an outer poe task that runs
    poe again) doesn't leak into a task that received no free arguments.
    """
    result = run_poe(
        "echo-extra-args", project="cmds", env={"POE_EXTRA_ARGS": "from-outer"}
    )
    assert result.capture == "Poe => poe_test_echo extra:\n"
    assert result.stdout == "extra:\n"

    result = run_poe(
        "echo-extra-args",
        "mine",
        project="cmds",
        env={"POE_EXTRA_ARGS": "from-outer"},
    )
    assert result.capture == "Poe => poe_test_echo extra: mine\n"
    assert result.stdout == "extra: mine\n"
