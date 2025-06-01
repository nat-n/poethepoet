import pytest


@pytest.fixture
def generate_pyproject(temp_pyproject):
    def generator(project_verbosity=0, task_verbosity=0):
        def inline_task(inline_verbosity: int) -> str:
            return (
                '{ cmd = "poe_test_echo inline_task '
                + str(inline_verbosity)
                + ' ${POE_VERBOSITY}", verbosity = '
                + str(inline_verbosity)
                + " }"
            )

        project_tmpl = f"""
        [tool.poe]
        verbosity = {project_verbosity}

        [tool.poe.tasks.default_task]
        cmd = '''
            poe_test_echo "cmd task inheriting default verbosity {project_verbosity} $POE_VERBOSITY"
        '''

        [tool.poe.tasks.override_task]
        cmd = '''poe_test_echo "cmd task with verbosity {task_verbosity} $POE_VERBOSITY"'''
        verbosity = {task_verbosity}

        [tool.poe.tasks.seq_task]
        sequence = [
            "default_task",
            {inline_task(-2)},
            {inline_task(-1)},
            {inline_task(0)},
            {inline_task(1)},
            {inline_task(2)}
        ]
        verbosity = {task_verbosity}

        [tool.poe.tasks.switch_task]
        control = "poe_test_echo $control_option"
        args = ["control_option"]
            [[tool.poe.tasks.switch_task.switch]]
            case = "override_verbosity_up"
            cmd = "poe_test_echo 'task verbosity up'"
            verbosity = 2
            [[tool.poe.tasks.switch_task.switch]]
            case = "override_verbosity_down"
            cmd = "poe_test_echo 'task verbosity down'"
            verbosity = -2
            [[tool.poe.tasks.switch_task.switch]]
            cmd = "poe_test_echo 'default verbosity'"
        """  # noqa: E501

        return temp_pyproject(project_tmpl)

    return generator


def test_task_vs_project_verbosity(generate_pyproject, run_poe_subproc):
    # with override down
    project_path = generate_pyproject(project_verbosity=0, task_verbosity=-1)
    result = run_poe_subproc("default_task", cwd=project_path)
    assert (
        result.capture
        == "Poe => poe_test_echo 'cmd task inheriting default verbosity 0 0'\n"
    )
    assert result.stdout == "cmd task inheriting default verbosity 0 0\n"

    result = run_poe_subproc("override_task", cwd=project_path)
    assert result.capture == ""
    assert result.stdout == "cmd task with verbosity -1 -1\n"

    # # with override up
    project_path = generate_pyproject(project_verbosity=-1, task_verbosity=0)
    result = run_poe_subproc("default_task", cwd=project_path)
    assert result.capture == ""
    assert result.stdout == "cmd task inheriting default verbosity -1 -1\n"

    result = run_poe_subproc("override_task", cwd=project_path)
    assert result.capture == "Poe => poe_test_echo 'cmd task with verbosity 0 0'\n"
    assert result.stdout == "cmd task with verbosity 0 0\n"


def test_override_verbosity_with_cli(generate_pyproject, run_poe_subproc):
    # with override up
    project_path = generate_pyproject(project_verbosity=-1, task_verbosity=-2)
    result = run_poe_subproc("-v", "default_task", cwd=project_path)
    assert (
        result.capture
        == "Poe => poe_test_echo 'cmd task inheriting default verbosity -1 0'\n"
    )
    assert result.stdout == "cmd task inheriting default verbosity -1 0\n"

    result = run_poe_subproc("-v", "override_task", cwd=project_path)
    assert result.capture == ""
    assert result.stdout == "cmd task with verbosity -2 -1\n"

    result = run_poe_subproc("-vv", "default_task", cwd=project_path)
    assert (
        result.capture
        == "Poe => poe_test_echo 'cmd task inheriting default verbosity -1 1'\n"
    )
    assert result.stdout == "cmd task inheriting default verbosity -1 1\n"

    result = run_poe_subproc("-vv", "override_task", cwd=project_path)
    assert result.capture == "Poe => poe_test_echo 'cmd task with verbosity -2 0'\n"
    assert result.stdout == "cmd task with verbosity -2 0\n"

    result = run_poe_subproc("-vvv", "override_task", cwd=project_path)
    assert result.capture == "Poe => poe_test_echo 'cmd task with verbosity -2 1'\n"
    assert result.stdout == "cmd task with verbosity -2 1\n"

    # with override down
    project_path = generate_pyproject(project_verbosity=1, task_verbosity=2)

    result = run_poe_subproc("-q", "default_task", cwd=project_path)
    assert (
        result.capture
        == "Poe => poe_test_echo 'cmd task inheriting default verbosity 1 0'\n"
    )
    assert result.stdout == "cmd task inheriting default verbosity 1 0\n"

    result = run_poe_subproc("-q", "override_task", cwd=project_path)
    assert result.capture == "Poe => poe_test_echo 'cmd task with verbosity 2 1'\n"
    assert result.stdout == "cmd task with verbosity 2 1\n"

    result = run_poe_subproc("-qq", "default_task", cwd=project_path)
    assert result.capture == ""
    assert result.stdout == "cmd task inheriting default verbosity 1 -1\n"

    result = run_poe_subproc("-qq", "override_task", cwd=project_path)
    assert result.capture == "Poe => poe_test_echo 'cmd task with verbosity 2 0'\n"
    assert result.stdout == "cmd task with verbosity 2 0\n"

    result = run_poe_subproc("-qqq", "override_task", cwd=project_path)
    assert result.capture == ""
    assert result.stdout == "cmd task with verbosity 2 -1\n"


def test_sequence_task_with_verbosity(generate_pyproject, run_poe_subproc):
    project_path = generate_pyproject()
    result = run_poe_subproc("seq_task", cwd=project_path)
    assert result.capture == (
        "Poe => poe_test_echo 'cmd task inheriting default verbosity 0 0'\n"
        "Poe => poe_test_echo inline_task 0 0\n"
        "Poe => poe_test_echo inline_task 1 1\n"
        "Poe => poe_test_echo inline_task 2 2\n"
    )
    assert result.stdout == (
        "cmd task inheriting default verbosity 0 0\n"
        "inline_task -2 -2\n"
        "inline_task -1 -1\n"
        "inline_task 0 0\n"
        "inline_task 1 1\n"
        "inline_task 2 2\n"
    )

    project_path = generate_pyproject(project_verbosity=-1)
    result = run_poe_subproc("seq_task", cwd=project_path)
    assert result.capture == (
        "Poe => poe_test_echo 'cmd task inheriting default verbosity -1 0'\n"
        "Poe => poe_test_echo inline_task 0 0\n"
        "Poe => poe_test_echo inline_task 1 1\n"
        "Poe => poe_test_echo inline_task 2 2\n"
    )
    assert result.stdout == (
        "cmd task inheriting default verbosity -1 0\n"
        "inline_task -2 -2\n"
        "inline_task -1 -1\n"
        "inline_task 0 0\n"
        "inline_task 1 1\n"
        "inline_task 2 2\n"
    )


def test_switch_task_with_verbosity(generate_pyproject, run_poe_subproc):
    project_path = generate_pyproject()
    result = run_poe_subproc("switch_task", cwd=project_path)
    assert result.capture == (
        "Poe <= poe_test_echo\nPoe => poe_test_echo 'default verbosity'\n"
    )
    assert result.stdout == "default verbosity\n"

    result = run_poe_subproc(
        "switch_task", "--control_option=override_verbosity_up", cwd=project_path
    )
    assert result.capture == (
        "Poe <= poe_test_echo override_verbosity_up\n"
        "Poe => poe_test_echo 'task verbosity up'\n"
    )
    assert result.stdout == "task verbosity up\n"

    result = run_poe_subproc(
        "switch_task", "--control_option=override_verbosity_down", cwd=project_path
    )
    assert result.capture == ("Poe <= poe_test_echo override_verbosity_down\n")
    assert result.stdout == "task verbosity down\n"

    result = run_poe_subproc(
        "-qqq",
        "switch_task",
        "--control_option=override_verbosity_up",
        cwd=project_path,
    )
    assert result.capture == ""
    assert result.stdout == "task verbosity up\n"
