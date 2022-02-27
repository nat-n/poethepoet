from pathlib import Path
import pytest
import sys

PY_V = f"{sys.version_info.major}.{sys.version_info.minor}"


def test_virtualenv_executor_fails_without_venv_dir(run_poe_subproc, projects):
    venv_path = projects["venv"].joinpath("myvenv")
    print("venv_path", venv_path)
    assert (
        not venv_path.is_dir()
    ), f"This test requires the virtualenv not to already exist at {venv_path}!"
    result = run_poe_subproc("show_env", project="venv")
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
    for _ in with_virtualenv_and_venv(venv_path):
        result = run_poe_subproc("show_env", project="venv")
        assert result.capture == "Poe => env\n"
        assert f"VIRTUAL_ENV={venv_path}" in result.stdout
        assert result.stderr == ""


@pytest.mark.slow
def test_virtualenv_executor_provides_access_to_venv_content(
    run_poe_subproc, with_virtualenv_and_venv, projects
):
    # version 1.0.0 of flask isn't around much
    venv_path = projects["venv"].joinpath("myvenv")
    for _ in with_virtualenv_and_venv(
        venv_path, ["itsdangerous==2.0.1", "flask==1.0.0"]
    ):
        # binaries from the venv are directly callable
        result = run_poe_subproc("server-version", project="venv")
        assert result.capture == "Poe => flask --version\n"
        assert "Flask 1.0" in result.stdout
        assert result.stderr == ""
        # python packages from the venv are importable
        result = run_poe_subproc("flask-version", project="venv")
        assert result.capture == "Poe => flask-version\n"
        assert result.stdout == "1.0\n"
        assert result.stderr == ""
        # binaries from the venv are on the path
        result = run_poe_subproc("server-version2", project="venv")
        assert result.capture == "Poe => server-version2\n"
        assert "Flask 1.0" in result.stdout
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
        result = run_poe_subproc("detect_flask", project="simple")
        assert result.capture == "Poe => detect_flask\n"
        assert result.stdout == "No flask found\n"
        assert result.stderr == ""

        # if we install flask into this virtualenv then we should get a different result
        install_into_virtualenv(venv_path, ["itsdangerous==2.0.1", "flask==1.0.0"])
        result = run_poe_subproc("detect_flask", project="simple")
        assert result.capture == "Poe => detect_flask\n"
        assert result.stdout.startswith("Flask found at ")
        if is_windows:
            assert result.stdout.endswith(
                f"\\tests\\fixtures\\simple_project\\venv\\lib\\site-packages\\flask\\__init__.py\n"
            )
        else:
            assert result.stdout.endswith(
                f"/tests/fixtures/simple_project/venv/lib/python{PY_V}/site-packages/flask/__init__.py\n"
            )
        assert result.stderr == ""


def test_simple_exector(run_poe_subproc):
    """
    The task should execute but not find flask from a local venv
    """
    result = run_poe_subproc("detect_flask", project="simple")
    assert result.capture == "Poe => detect_flask\n"
    assert result.stdout == "No flask found\n" or not result.stdout.endswith(
        f"/tests/fixtures/simple_project/venv/lib/python{PY_V}/site-packages/flask/__init__.py\n"
    )
    assert result.stderr == ""
