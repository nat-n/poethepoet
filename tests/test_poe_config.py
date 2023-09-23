# Setting POETRY_VIRTUALENVS_CREATE stops poetry from creating the virtualenv and
# spamming about it in stdout
no_venv = {"POETRY_VIRTUALENVS_CREATE": "false"}


def test_setting_default_task_type(run_poe_subproc, projects, esc_prefix):
    # Also tests passing of extra_args to sys.argv
    result = run_poe_subproc(
        "echo-args",
        "nat,",
        r"welcome to " + esc_prefix + "${POE_ROOT}",
        project="scripts",
        env=no_venv,
    )
    assert result.capture == f"Poe => echo-args nat, welcome to {projects['scripts']}\n"
    assert result.stdout == f"hello nat, welcome to {projects['scripts']}\n"
    assert result.stderr == ""


def test_setting_default_array_item_task_type(run_poe_subproc):
    result = run_poe_subproc("composite_task", project="scripts", env=no_venv)
    assert result.capture == "Poe => poe_test_echo Hello\nPoe => poe_test_echo World!\n"
    assert result.stdout == "Hello\nWorld!\n"
    assert result.stderr == ""


def test_setting_global_env_vars(run_poe_subproc):
    result = run_poe_subproc("travel", env=no_venv)
    assert result.capture == "Poe => poe_test_echo from EARTH to\nPoe => travel[1]\n"
    assert result.stdout == "from EARTH to\nMARS\n"
    assert result.stderr == ""


def test_setting_default_verbosity(run_poe_subproc, low_verbosity_project_path):
    result = run_poe_subproc(
        "test",
        cwd=low_verbosity_project_path,
    )
    assert result.capture == ""
    assert result.stdout == "Hello there!\n"
    assert result.stderr == ""


def test_override_default_verbosity(run_poe_subproc, low_verbosity_project_path):
    result = run_poe_subproc(
        "-v",
        "-v",
        "test",
        cwd=low_verbosity_project_path,
    )
    assert result.capture == "Poe => poe_test_echo Hello there!\n"
    assert result.stdout == "Hello there!\n"
    assert result.stderr == ""


def test_partially_decrease_verbosity(run_poe_subproc, high_verbosity_project_path):
    result = run_poe_subproc(
        "-q",
        "test",
        cwd=high_verbosity_project_path,
    )
    assert result.capture == "Poe => poe_test_echo Hello there!\n"
    assert result.stdout == "Hello there!\n"
    assert result.stderr == ""


def test_decrease_verbosity(run_poe_subproc):
    result = run_poe_subproc(
        "-q",
        "part1",
        env=no_venv,
    )
    assert result.capture == ""
    assert result.stderr == ""
    assert result.stdout == "Hello\n"
