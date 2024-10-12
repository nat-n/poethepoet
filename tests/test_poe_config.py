# Setting POETRY_VIRTUALENVS_CREATE stops poetry from creating the virtualenv and
# spamming about it in stderr
poetry_vars = {"POETRY_VIRTUALENVS_CREATE": "false"}


def test_setting_default_task_type(run_poe_subproc, projects, esc_prefix):
    # Also tests passing of extra_args to sys.argv
    result = run_poe_subproc(
        "echo-args",
        "nat,",
        r"welcome to " + esc_prefix + "${POE_ROOT}",
        project="scripts",
        env=poetry_vars,
    )
    assert (
        result.capture == f"Poe => echo-args nat, 'welcome to {projects['scripts']}'\n"
    )
    assert result.stdout == f"hello nat, welcome to {projects['scripts']}\n"
    result.assert_no_err()


def test_setting_default_array_item_task_type(run_poe_subproc):
    result = run_poe_subproc(
        "composite_task", project="scripts", env={"POETRY_VIRTUALENVS_CREATE": "false"}
    )
    assert (
        result.capture == "Poe => poe_test_echo Hello\nPoe => poe_test_echo 'World!'\n"
    )
    assert result.stdout == "Hello\nWorld!\n"
    result.assert_no_err()


def test_setting_global_env_vars(run_poe_subproc):
    result = run_poe_subproc("travel", env=poetry_vars)
    assert (
        result.capture == "Poe => poe_test_echo 'from EARTH to'\nPoe => 'travel[1]'\n"
    )
    assert result.stdout == "from EARTH to\nMARS\n"
    result.assert_no_err()


def test_setting_default_verbosity(run_poe_subproc, low_verbosity_project_path):
    result = run_poe_subproc(
        "test",
        cwd=low_verbosity_project_path,
    )
    assert result.capture == ""
    assert result.stdout == "Hello there!\n"
    result.assert_no_err()


def test_override_default_verbosity(run_poe_subproc, low_verbosity_project_path):
    result = run_poe_subproc(
        "-v",
        "-v",
        "test",
        cwd=low_verbosity_project_path,
    )
    assert result.capture == "Poe => poe_test_echo Hello 'there!'\n"
    assert result.stdout == "Hello there!\n"
    result.assert_no_err()


def test_partially_decrease_verbosity(run_poe_subproc, high_verbosity_project_path):
    result = run_poe_subproc(
        "-q",
        "test",
        cwd=high_verbosity_project_path,
    )
    assert result.capture == "Poe => poe_test_echo Hello 'there!'\n"
    assert result.stdout == "Hello there!\n"
    result.assert_no_err()


def test_decrease_verbosity(run_poe_subproc):
    result = run_poe_subproc("-q", "part1", env=poetry_vars)
    assert result.capture == ""
    assert result.stdout == "Hello\n"
    result.assert_no_err()
