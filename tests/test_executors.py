import sys

import pytest

PY_V = f"{sys.version_info.major}.{sys.version_info.minor}"


def test_virtualenv_executor_fails_without_venv_dir(run_poe_subproc, projects):
    venv_path = projects["venv"].joinpath("myvenv")
    assert (
        not venv_path.is_dir()
    ), f"This test requires the virtualenv not to already exist at {venv_path}!"
    result = run_poe_subproc("show-env", project="venv")
    assert (
        f"Error: Could not find valid virtualenv at configured location: {venv_path}"
        in result.capture
    )
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.slow
def test_virtualenv_executor_activates_venv(
    run_poe_subproc, with_virtualenv_and_venv, projects
):
    venv_path = projects["venv"].joinpath("myvenv")
    for _ in with_virtualenv_and_venv(
        venv_path, ["./tests/fixtures/packages/poe_test_helpers"]
    ):
        result = run_poe_subproc("show-env", project="venv")
        assert result.capture == "Poe => poe_test_env\n"
        assert f"VIRTUAL_ENV={venv_path}" in result.stdout
        assert result.stderr == ""


@pytest.mark.slow
def test_virtualenv_executor_provides_access_to_venv_content(
    run_poe_subproc, with_virtualenv_and_venv, projects
):
    # Create a venv containing our special test package
    venv_path = projects["venv"].joinpath("myvenv")
    for _ in with_virtualenv_and_venv(
        venv_path,
        ("./tests/fixtures/packages/poe_test_package",),
    ):
        # binaries from the venv are directly callable
        result = run_poe_subproc("show-version", project="venv")
        assert result.capture == "Poe => test_print_version\n"
        assert "Poe test package 0.0.99" in result.stdout
        assert result.stderr == ""

        # python packages from the venv are importable
        result = run_poe_subproc("test-package-version", project="venv")
        assert result.capture == "Poe => test-package-version\n"
        assert result.stdout == "0.0.99\n"
        assert result.stderr == ""

        # binaries from the venv are on the path
        result = run_poe_subproc("test-package-exec-version", project="venv")
        assert result.capture == "Poe => test-package-exec-version\n"
        assert "Poe test package 0.0.99" in result.stdout
        assert result.stderr == ""


@pytest.mark.slow
def test_detect_venv(
    projects,
    run_poe_subproc,
    install_into_virtualenv,
    with_virtualenv_and_venv,
    is_windows,
):
    """
    If no executor is specified and no poetry config is present but a local venv is
    found then use it!
    """
    venv_path = projects["simple"].joinpath("venv")
    for _ in with_virtualenv_and_venv(venv_path):
        result = run_poe_subproc("detect_poe_test_package", project="simple")
        assert result.capture == "Poe => detect_poe_test_package\n"
        assert result.stdout == "No poe_test_package found\n"
        assert result.stderr == ""

        # if we install poe_test_package into this virtualenv then we should get a
        # different result
        install_into_virtualenv(
            venv_path, ("./tests/fixtures/packages/poe_test_package",)
        )
        result = run_poe_subproc("detect_poe_test_package", project="simple")
        assert result.capture == "Poe => detect_poe_test_package\n"
        assert result.stdout.startswith("poe_test_package found at ")
        if is_windows:
            assert result.stdout.endswith(
                (
                    "\\tests\\fixtures\\simple_project\\venv\\lib\\site-packages"
                    "\\poe_test_package\\__init__.py\n",
                    # Lib has a captital with python >=11
                    "\\tests\\fixtures\\simple_project\\venv\\Lib\\site-packages"
                    "\\poe_test_package\\__init__.py\n",
                )
            )
        else:
            assert result.stdout.endswith(
                f"/tests/fixtures/simple_project/venv/lib/python{PY_V}"
                "/site-packages/poe_test_package/__init__.py\n"
            )
        assert result.stderr == ""


def test_simple_executor(run_poe_subproc):
    """
    The task should execute but not find poe_test_package from a local venv
    """
    result = run_poe_subproc("detect_poe_test_package", project="simple")
    assert result.capture == "Poe => detect_poe_test_package\n"
    assert result.stdout == "No poe_test_package found\n" or not result.stdout.endswith(
        f"/tests/fixtures/simple_project/venv/lib/python{PY_V}/site-packages/poe_test_package/__init__.py\n"
    )
    assert result.stderr == ""


def test_override_executor(run_poe_subproc, with_virtualenv_and_venv, projects):
    """
    This test includes two scenarios

    1. A variation on test_virtualenv_executor_fails_without_venv_dir except that
       because we force use of the simple executor we don't get the error

    2. A variation on test_virtualenv_executor_activates_venv except that because we
       force use of the simple executor we don't get the virtual_env
    """

    # 1.
    venv_path = projects["venv"].joinpath("myvenv")
    assert (
        not venv_path.is_dir()
    ), f"This test requires the virtualenv not to already exist at {venv_path}!"
    result = run_poe_subproc("--executor", "simple", "show-env", project="venv")
    assert (
        f"Error: Could not find valid virtualenv at configured location: {venv_path}"
        not in result.capture
    )
    assert result.stderr == ""

    # 2.
    venv_path = projects["venv"].joinpath("myvenv")
    for _ in with_virtualenv_and_venv(
        venv_path, ["./tests/fixtures/packages/poe_test_helpers"]
    ):
        result = run_poe_subproc("-e", "simple", "show-env", project="venv")
        assert result.capture == "Poe => poe_test_env\n"
        assert f"VIRTUAL_ENV={venv_path}" not in result.stdout
        assert result.stderr == ""
