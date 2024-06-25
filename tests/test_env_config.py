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


def test_global_env_templating(temp_pyproject, run_poe_subproc):
    project_path = temp_pyproject(EXAMPLE_CONFIG)
    result = run_poe_subproc("my-task", cwd=project_path)
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


def test_substitution_in_envvar(temp_pyproject, run_poe_subproc):
    project_path = temp_pyproject(EXAMPLE_WITH_ENV_COMPOSITION)
    result = run_poe_subproc("frobnicate", cwd=project_path)

    assert result.capture == "Poe => ${FILE}\n"
    assert result.stdout == "/foo/bar/baz\n"
    assert result.stderr == ""
