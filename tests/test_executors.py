import os
import sys
from pathlib import Path

import pytest

from poethepoet.virtualenv import Virtualenv

PY_V = f"{sys.version_info.major}.{sys.version_info.minor}"


@pytest.fixture(params=("use_venv", "use_virtualenv"), ids=("venv", "virtualenv"))
def venv_creator(request):
    return request.getfixturevalue(request.param)


def test_virtualenv_executor_fails_without_venv_dir(run_poe, projects):
    venv_path = projects["venv"].joinpath("myvenv")
    assert not venv_path.is_dir(), (
        f"This test requires the virtualenv not to already exist at {venv_path}!"
    )
    result = run_poe("show-env", project="venv")
    assert (
        f"Error: Could not find valid virtualenv at configured location: {venv_path}"
        in result.capture
    )
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.slow
def test_virtualenv_executor_activates_venv(run_poe_subproc, venv_creator, projects):
    venv_path = projects["venv"].joinpath("myvenv")
    with venv_creator(
        venv_path,
        ["./tests/fixtures/packages/poe_test_helpers"],
        require_empty=True,
    ):
        result = run_poe_subproc("show-env", project="venv")
        assert result.capture == "Poe => poe_test_env\n"
        assert f"VIRTUAL_ENV={venv_path}" in result.stdout
        assert result.stderr == ""


@pytest.mark.slow
def test_override_executor_config_on_task(run_poe_subproc, use_venv, projects):
    """
    Rely on task level config to correctly set the virtualenv location
    """
    venv_path = projects["venv"].joinpath("my_other_venv")
    with use_venv(venv_path, ["./tests/fixtures/packages/poe_test_helpers"]):
        result = run_poe_subproc("override-executor-on-task", project="venv")
        assert result.capture == "Poe => poe_test_env\n"
        assert f"VIRTUAL_ENV={venv_path}" in result.stdout
        assert result.stderr == ""


@pytest.mark.slow
def test_override_executor_config_on_cli(run_poe_subproc, use_venv, projects):
    """
    Rely on executor config override from the --executor-opt options to correctly set
    the virtualenv location
    """
    venv_path = projects["venv"].joinpath("my_other_venv")
    with use_venv(venv_path, ["./tests/fixtures/packages/poe_test_helpers"]):
        result = run_poe_subproc(
            "--executor-opt", f"location={venv_path}", "show-env", project="venv"
        )
        assert result.capture == "Poe => poe_test_env\n"
        assert f"VIRTUAL_ENV={venv_path}" in result.stdout
        assert result.stderr == ""


def test_override_executor_config(run_poe):
    """
    Rely on task level config to correctly set the virtualenv location
    """
    result = run_poe("override-executor", project="venv")
    assert result.capture == "Poe => poe_test_env\n"
    assert "POE_ACTIVE=simple" in result.stdout
    assert result.stderr == ""


def test_override_executor_with_cli(run_poe, projects):
    result = run_poe("-e", "simple", "show-env", project="venv")
    assert result.capture == "Poe => poe_test_env\n"
    assert "POE_ACTIVE=simple" in result.stdout
    assert result.stderr == ""


@pytest.mark.slow
def test_virtualenv_executor_provides_access_to_venv_content(
    run_poe_subproc, use_venv, projects
):
    # Create a venv containing our special test package
    venv_path = projects["venv"].joinpath("myvenv")
    with use_venv(
        venv_path,
        ("./tests/fixtures/packages/poe_test_package",),
        require_empty=True,
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
    venv_creator,
    is_windows,
):
    """
    If no executor is specified and no poetry config is present but a local venv is
    found then use it!
    """
    venv_path = projects["simple"].joinpath("venv")
    with venv_creator(venv_path, require_empty=True):
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


def test_simple_executor(run_poe):
    """
    The task should execute but not find poe_test_package from a local venv
    """
    result = run_poe("detect_poe_test_package", project="simple")
    assert result.capture == "Poe => detect_poe_test_package\n"
    assert result.stdout == "No poe_test_package found\n" or not result.stdout.endswith(
        f"/tests/fixtures/simple_project/venv/lib/python{PY_V}/site-packages/poe_test_package/__init__.py\n"
    )
    assert result.stderr == ""


def test_override_executor_skips_missing_virtualenv_when_forced_simple(
    run_poe, projects
):
    """
    Forcing the simple executor should bypass a broken project-level virtualenv
    configuration.
    """
    venv_path = projects["venv"].joinpath("myvenv")
    assert not venv_path.is_dir(), (
        f"This test requires the virtualenv not to already exist at {venv_path}!"
    )
    result = run_poe("--executor", "simple", "show-env", project="venv")
    assert (
        f"Error: Could not find valid virtualenv at configured location: {venv_path}"
        not in result.capture
    )
    assert result.stderr == ""


@pytest.mark.slow
def test_override_executor_skips_existing_virtualenv_when_forced_simple(
    run_poe_subproc, use_virtualenv, projects
):
    """
    Forcing the simple executor should ignore an otherwise valid virtualenv.
    """
    venv_path = projects["venv"].joinpath("myvenv")
    with use_virtualenv(
        venv_path,
        ["./tests/fixtures/packages/poe_test_helpers"],
        require_empty=True,
    ):
        result = run_poe_subproc("-e", "simple", "show-env", project="venv")
        assert result.capture == "Poe => poe_test_env\n"
        assert f"VIRTUAL_ENV={venv_path}" not in result.stdout
        assert result.stderr == ""


def test_poetry_executor_without_poetry_installed(run_poe, tmp_path):
    """
    Forcing the poetry executor when poetry is not available gives a clear error
    """
    result = run_poe(
        "-e",
        "poetry",
        "show-env",
        project="simple_executor",
        env={"PATH": str(tmp_path)},
    )
    assert result.code == 1
    assert result.capture == (
        "Poe => poe_test_env\n"
        "Error: executable 'poetry' could not be found, but is required by the "
        "poetry executor\n"
        "     | From: FileNotFoundError(2, 'No such file or directory')\n"
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_global_executor_config(run_poe):
    """
    Rely on global config to correctly
    """
    result = run_poe("show-env", project="simple_executor")
    assert result.capture == "Poe => poe_test_env\n"
    assert "POE_ACTIVE=simple" in result.stdout
    assert result.stderr == ""


def test_global_executor_config_rejects_unknown_keys(temp_pyproject, run_poe):
    """
    Unknown keys in tool.poe.executor must be rejected by validate_config at
    config-parse time (regression test for #390).

    Before the fix, validate_config silently accepted the bogus key (the
    generator returned by ExecutorOptions.parse was never iterated) and the
    error only surfaced later — wrapped — when PoeExecutor.get() finally
    consumed the generator. The cleaner unwrapped error message confirms
    validate_config itself raised.
    """
    project_path = temp_pyproject("""
            [tool.poe.executor]
            type = "simple"
            extra_bogus = "should be rejected"

            [tool.poe.tasks]
            greet = "poe_test_echo hi"
        """)
    result = run_poe("-d", "greet", cwd=project_path)
    assert result.code == 1
    assert "Error: Unrecognized option 'extra_bogus'" in result.capture
    # The wrapped form would be "Couldn't parse executor options …" — that
    # would mean PoeExecutor.get() caught it instead of validate_config.
    assert "Couldn't parse executor options" not in result.capture
    assert result.stdout == ""


def test_global_executor_config_rejects_wrong_value_type(temp_pyproject, run_poe):
    """
    The same generator-not-consumed bug that hid unknown keys also hid the
    per-field value_type.validate(...) checks inside PoeOptions.parse. This
    locks in that value-type errors on executor configs surface from
    validate_config too (companion to #390).

    Uses a bool value for `location` — accepted by the outer ConfigOptions
    schema (which allows str/list[str]/bool for executor option values) but
    invalid against the inner virtualenv ExecutorOptions schema (str | None).
    Without the fix, the inner check is skipped and the error never surfaces.
    """
    project_path = temp_pyproject("""
            [tool.poe.executor]
            type = "virtualenv"
            location = true

            [tool.poe.tasks]
            greet = "poe_test_echo hi"
        """)
    result = run_poe("-d", "greet", cwd=project_path)
    assert result.code == 1
    assert "Option 'location' must have a value of type" in result.capture
    assert "Couldn't parse executor options" not in result.capture
    assert result.stdout == ""


def _make_fake_virtualenv(location: Path) -> Path:
    """
    Create the minimal file structure that poe recognises as a posix virtualenv
    """
    bin_dir = location / "bin"
    bin_dir.mkdir(parents=True)
    bin_dir.joinpath("activate").touch()
    bin_dir.joinpath("python").touch()
    location.joinpath("lib", f"python{PY_V}", "site-packages").mkdir(parents=True)
    return bin_dir


def _make_shell_script(bin_dir: Path, name: str, content: str) -> Path:
    """
    Create an executable posix shell script with the given content
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    executable = bin_dir / name
    executable.write_text(f"#!/bin/sh\n{content}\n")
    executable.chmod(0o755)
    return executable


def test_virtualenv_get_env_vars_extends_given_path(tmp_path):
    """
    The venv bin dir is prepended to the PATH from the given env, not os.environ
    """
    venv = Virtualenv(tmp_path / "venv")
    base_path = os.pathsep.join(["/custom/bin", "/usr/bin"])

    result = venv.get_env_vars({"PATH": base_path, "PYTHONHOME": "/py/home"})

    assert result["PATH"] == os.pathsep.join([str(venv.bin_dir()), base_path])
    assert result["VIRTUAL_ENV"] == str(venv.path)
    assert result["_OLD_VIRTUAL_PATH"] == base_path
    assert "PYTHONHOME" not in result
    assert result["_OLD_VIRTUAL_PYTHONHOME"] == "/py/home"


def test_virtualenv_get_env_vars_replaces_active_venv(tmp_path):
    """
    The bin dir of another active virtualenv is removed from the PATH
    """
    venv = Virtualenv(tmp_path / "venv")
    active_venv = Virtualenv(tmp_path / "active_venv")
    base_path = os.pathsep.join(["/custom/bin", str(active_venv.bin_dir()), "/usr/bin"])

    result = venv.get_env_vars(
        {"PATH": base_path, "VIRTUAL_ENV": str(active_venv.path)}
    )

    expected_old_path = os.pathsep.join(["/custom/bin", "/usr/bin"])
    assert result["PATH"] == os.pathsep.join([str(venv.bin_dir()), expected_old_path])
    assert result["VIRTUAL_ENV"] == str(venv.path)
    assert result["_OLD_VIRTUAL_PATH"] == expected_old_path


def test_virtualenv_get_env_vars_doesnt_duplicate_bin_dir(tmp_path):
    """
    The venv bin dir is not prepended again if it is already first on the PATH
    """
    venv = Virtualenv(tmp_path / "venv")
    base_path = os.pathsep.join([str(venv.bin_dir()), "/usr/bin"])

    result = venv.get_env_vars({"PATH": base_path})

    assert result["PATH"] == base_path


@pytest.mark.skipif(sys.platform == "win32", reason="Uses a posix shell script")
def test_virtualenv_executor_keeps_task_path(run_poe, temp_pyproject, tmp_path):
    """
    A PATH set in the task env reaches the subprocess, behind the venv bin dir
    """
    venv_bin = _make_fake_virtualenv(tmp_path / "fake_venv")
    custom_bin = tmp_path / "custom_bin"
    _make_shell_script(custom_bin, "only_on_task_path", "echo found it")
    project_path = temp_pyproject(f"""
            [tool.poe.executor]
            type = "virtualenv"
            location = "{venv_bin.parent.as_posix()}"

            [tool.poe.tasks.custom-bin]
            cmd = "only_on_task_path"
            env = {{ PATH = "{custom_bin.as_posix()}:${{PATH}}" }}

            [tool.poe.tasks.show-path]
            cmd = "poe_test_env"
            env = {{ PATH = "{custom_bin.as_posix()}:${{PATH}}" }}
        """)

    result = run_poe("custom-bin", cwd=project_path)
    assert result.capture == "Poe => only_on_task_path\n"
    assert result.stdout == "found it\n"
    assert result.stderr == ""

    result = run_poe("show-path", cwd=project_path)
    assert result.capture == "Poe => poe_test_env\n"
    assert f"PATH={venv_bin}:{custom_bin}:" in result.stdout
    assert result.stderr == ""
