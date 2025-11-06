import os
import shutil
from pathlib import Path


_STUB_PATH = Path(__file__).parent / "stubs"


def _stub_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    pythonpath = os.pathsep.join(
        filter(None, [str(_STUB_PATH), os.environ.get("PYTHONPATH")])
    )
    env = {"PYTHONPATH": pythonpath}
    if extra:
        env.update(extra)
    return env


def _copy_fixture_project(projects, project_key: str, tmp_path: Path) -> Path:
    destination = tmp_path / f"{project_key.replace('/', '_')}_copy"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(projects[project_key], destination)
    return destination


def test_optional_envfile_missing(run_poe_subproc, projects, tmp_path):
    project_path = _copy_fixture_project(projects, "envfile_optional", tmp_path)

    optional_env = project_path / ".env"
    if optional_env.exists():
        optional_env.unlink()

    result = run_poe_subproc(
        "print-var",
        cwd=str(project_path),
        coverage=False,
        env=_stub_env(),
    )

    assert result.code == 0
    assert "Poe failed to locate envfile" not in result.stderr
    assert "Poe failed to locate envfile" not in result.capture
    assert result.stdout == "missing\n"


def test_optional_envfile_loaded_when_present(run_poe_subproc, projects, tmp_path):
    project_path = _copy_fixture_project(projects, "envfile_optional", tmp_path)
    optional_env = project_path / ".env"
    optional_env.write_text("FROM_ENV=42\n", encoding="utf-8")

    result = run_poe_subproc(
        "print-var",
        cwd=str(project_path),
        coverage=False,
        env=_stub_env(),
    )

    assert result.code == 0
    assert result.stdout == "42\n"
    assert "Poe failed to locate envfile" not in result.stderr
