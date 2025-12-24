import os
import shutil

import pytest


def _uv_integration_available():
    if not shutil.which("uv"):
        return False
    try:
        import socket

        sock = socket.create_connection(("pypi.org", 443), timeout=1)
    except OSError:
        return False
    else:
        sock.close()
        return True


UV_INTEGRATION_AVAILABLE = _uv_integration_available()
UV_RUN_OPTION_SET = {
    "run",
    "--extra=dev",
    "--group=ci",
    "--group=docs",
    "--no-group=local",
    "--with=http",
    "--with=tls",
    "--python=3.12",
    "--isolated",
    "--no-sync",
    "--locked",
    "--frozen",
    "--no-project",
}


@pytest.fixture
def mock_uv_path(tmp_path, is_windows):
    tmp_dir = tmp_path / "mock_uv"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    if is_windows:
        uv_path = tmp_dir / "uv.bat"
        uv_path.write_text(
            "@echo off\r\n"
            ":loop\r\n"
            'if "%~1"=="" goto :eof\r\n'
            "echo %~1\r\n"
            "shift\r\n"
            "goto loop\r\n"
        )
    else:
        uv_path = tmp_dir / "uv"
        uv_path.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
        uv_path.chmod(0o755)
    return tmp_dir


@pytest.fixture
def uv_cache_env(tmp_path):
    xdg_cache = tmp_path / "xdg_cache"
    uv_cache = tmp_path / "uv_cache"
    xdg_cache.mkdir(parents=True, exist_ok=True)
    uv_cache.mkdir(parents=True, exist_ok=True)
    return {
        "XDG_CACHE_HOME": str(xdg_cache),
        "UV_CACHE_DIR": str(uv_cache),
    }


@pytest.mark.skipif(
    not UV_INTEGRATION_AVAILABLE, reason="No uv available or network blocked"
)
def test_uv_package_script_task(run_poe_subproc, projects, uv_cache_env):
    result = run_poe_subproc("-q", "script-task", project="uv", env=uv_cache_env)

    assert result.capture == ""
    assert result.stderr == ""
    assert result.stdout == "Hello from uv-project 0.0.99\n"


@pytest.mark.skipif(
    not UV_INTEGRATION_AVAILABLE, reason="No uv available or network blocked"
)
def test_uv_executor_env(run_poe_subproc, projects, is_windows, uv_cache_env):
    result = run_poe_subproc("show-env", project="uv", env=uv_cache_env)

    assert result.capture == "Poe => poe_test_env\n"
    assert result.stderr == ""

    if is_windows:
        assert f"VIRTUAL_ENV={projects['uv']}\\.venv" in result.stdout
    else:
        assert f"VIRTUAL_ENV={projects['uv']}/.venv" in result.stdout
    assert "POE_ACTIVE=uv" in result.stdout


@pytest.mark.skipif(
    not UV_INTEGRATION_AVAILABLE, reason="No uv available or network blocked"
)
def test_uv_executor_task_with_cwd(
    run_poe_subproc, projects, poe_project_path, is_windows, uv_cache_env
):
    if is_windows:
        subproject_path = f"{projects['uv']}\\subproject"
        result = run_poe_subproc(
            "-C", subproject_path, "test-cwd", "..\\..", env=uv_cache_env
        )
    else:
        subproject_path = f"{projects['uv']}/subproject"
        result = run_poe_subproc(
            "-C", subproject_path, "test-cwd", "../..", env=uv_cache_env
        )

    assert result.capture == (
        "Poe => echo UV_RUN_RECURSION_DEPTH: $UV_RUN_RECURSION_DEPTH\n"
        "echo VIRTUAL_ENV: $VIRTUAL_ENV\n"
        "echo pwd: $(pwd)\n"
    )

    if is_windows:
        assert f"VIRTUAL_ENV: {subproject_path}\\.venv" in result.stdout
    else:
        assert f"VIRTUAL_ENV: {subproject_path}/.venv" in result.stdout
        assert f"pwd: {poe_project_path}/tests/fixtures\n" in result.stdout


def _normalize_uv_lines(lines):
    """Normalize uv stdout tokens into a list where flags and their values
    are combined as `--flag=value` when the output splits them onto two
    separate lines (happens on some Windows setups).
    """
    normalized = []
    i = 0
    while i < len(lines):
        cur = lines[i]
        if (
            cur.startswith("--")
            and "=" not in cur
            and i + 1 < len(lines)
            and not lines[i + 1].startswith("--")
        ):
            normalized.append(f"{cur}={lines[i+1]}")
            i += 2
        else:
            normalized.append(cur)
            i += 1
    return normalized


def _assert_uv_options_present(lines):
    """Assert that the expected UV run options are present in the
    normalized `lines` list. Accept both `--flag=value` and `--flag value`
    style outputs.
    """
    lines_set = set(lines)
    for expected in UV_RUN_OPTION_SET:
        if expected == "run":
            assert "run" in lines_set
        elif "=" in expected:
            assert expected in lines_set
        else:
            assert expected in lines_set or any(
                line.startswith(expected + "=") for line in lines
            )


def test_uv_executor_passes_uv_run_options(run_poe_subproc, mock_uv_path):
    env = {"PATH": f"{mock_uv_path}{os.pathsep}{os.environ.get('PATH', '')}"}

    result = run_poe_subproc("test-uv-run-options", project="uv", env=env)

    assert result.code == 0
    raw_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    lines = _normalize_uv_lines(raw_lines)
    _assert_uv_options_present(lines)
    assert lines.count("--group=ci") == 1
    assert lines.count("--group=docs") == 1


@pytest.mark.parametrize(
    ("executor_flag", "executor_opt_flag"),
    [("--executor", "--executor-opt"), ("-e", "-X")],
)
def test_uv_executor_passes_uv_run_options_from_cli(
    run_poe_subproc, mock_uv_path, executor_flag, executor_opt_flag
):
    env = {"PATH": f"{mock_uv_path}{os.pathsep}{os.environ.get('PATH', '')}"}

    result = run_poe_subproc(
        executor_flag,
        "uv",
        executor_opt_flag,
        "extra=dev",
        executor_opt_flag,
        "group=ci",
        executor_opt_flag,
        "group=docs",
        executor_opt_flag,
        "no-group=local",
        executor_opt_flag,
        "with=http",
        executor_opt_flag,
        "with=tls",
        executor_opt_flag,
        "python=3.12",
        executor_opt_flag,
        "isolated",
        executor_opt_flag,
        "no-sync",
        executor_opt_flag,
        "locked",
        executor_opt_flag,
        "frozen",
        executor_opt_flag,
        "no-project",
        "test-uv-run-options-cli",
        project="uv",
        env=env,
    )

    assert result.code == 0
    raw_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    lines = _normalize_uv_lines(raw_lines)
    _assert_uv_options_present(lines)
    assert lines.count("--group=ci") == 1
    assert lines.count("--group=docs") == 1
