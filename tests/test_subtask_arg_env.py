"""
Tests that a task run as a subtask resolves its arg defaults, and its deps/uses
invocations, against the env inherited from its parent task, consistently with
what the task's own command sees.
"""


def test_arg_default_sees_parent_task_env(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.serve]
        cmd = "poe_test_echo port=${port} SERVE_PORT=${SERVE_PORT:-unset}"
        args = [{ name = "port", default = "${SERVE_PORT:-8000}" }]

        [tool.poe.tasks.dev]
        sequence = ["serve"]
        env = { SERVE_PORT = "9000" }
        """)
    result = run_poe("dev", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "port=9000 SERVE_PORT=9000\n"

    # Calling the task directly is unaffected
    result = run_poe("serve", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "port=8000 SERVE_PORT=unset\n"


def test_arg_default_sees_parent_task_uses(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.get-version]
        cmd = "poe_test_echo 1.2.3"

        [tool.poe.tasks.tag]
        cmd = "poe_test_echo version=${version}"
        args = [{ name = "version", default = "${RELEASE_VERSION:-unknown}" }]

        [tool.poe.tasks.release]
        sequence = ["tag"]
        uses = { RELEASE_VERSION = "get-version" }
        """)
    result = run_poe("release", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout.endswith("version=1.2.3\n")


def test_arg_default_sees_parent_task_args(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.check]
        cmd = "poe_test_echo loud=${loud}"
        args = [{ name = "loud", type = "boolean", default = "${CHECK_LOUD}" }]

        [tool.poe.tasks.pipeline]
        sequence = ["check"]
        args = [{ name = "CHECK_LOUD", options = ["--loud"], type = "boolean" }]
        """)
    result = run_poe("pipeline", "--loud", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "loud=True\n"

    # A false boolean arg on the parent unsets the variable for its subtasks,
    # even if it is set on the host environment
    result = run_poe("pipeline", cwd=project_path, env={"CHECK_LOUD": "true"})
    assert result.code == 0, result.capture
    assert result.stdout == "loud=\n"


def test_uses_invocation_sees_parent_task_env(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.load]
        cmd = "poe_test_echo config-for-${target}"
        args = [{ name = "target", positional = true }]

        [tool.poe.tasks.show]
        cmd = "poe_test_echo cfg=${CFG}"
        uses = { CFG = "load ${DEPLOY_ENV:-dev}" }

        [tool.poe.tasks.deploy-staging]
        sequence = ["show"]
        env = { DEPLOY_ENV = "staging" }
        """)
    result = run_poe("deploy-staging", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout.endswith("cfg=config-for-staging\n")


def test_switch_case_arg_default_sees_switch_env(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.serve]
        control.expr = "'x'"
        switch = [{ cmd = "poe_test_echo port=${port}" }]
        env = { SERVE_PORT = "9000" }
        args = [{ name = "port", default = "${SERVE_PORT:-8000}" }]
        """)
    result = run_poe("serve", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "port=9000\n"


def test_deps_of_subtask_do_not_inherit_parent_task_env(temp_pyproject, run_poe):
    project_path = temp_pyproject("""
        [tool.poe.tasks.printer]
        cmd = "poe_test_echo dep SERVE_PORT=${SERVE_PORT:-unset}"

        [tool.poe.tasks.serve]
        cmd = "poe_test_echo port=${port}"
        deps = ["printer"]
        args = [{ name = "port", default = "${SERVE_PORT:-8000}" }]

        [tool.poe.tasks.dev]
        sequence = ["serve"]
        env = { SERVE_PORT = "9000" }
        """)
    result = run_poe("dev", cwd=project_path)
    assert result.code == 0, result.capture
    assert result.stdout == "dep SERVE_PORT=unset\nport=9000\n"
