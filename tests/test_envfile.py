from pathlib import Path
import sys


def test_global_envfile(run_poe_subproc, poe_project_path, is_windows):
    project_path = poe_project_path.joinpath("tests", "fixtures", "envfile")
    result = run_poe_subproc("deploy-dev", cwd=project_path)
    if is_windows:
        # On windows shlex works in non-POSIX mode which results in  quotes
        assert (
            'Poe => echo "deploying to admin:12345@dev.example.com"\n' in result.capture
        )
        assert result.stdout == '"deploying to admin:12345@dev.example.com"\n'
        assert result.stderr == ""
    else:
        assert (
            "Poe => echo deploying to admin:12345@dev.example.com\n" in result.capture
        )
        assert result.stdout == "deploying to admin:12345@dev.example.com\n"
        assert result.stderr == ""


def test_task_envfile(run_poe_subproc, poe_project_path, is_windows):
    project_path = poe_project_path.joinpath("tests", "fixtures", "envfile")
    result = run_poe_subproc("deploy-prod", cwd=project_path)
    if is_windows:
        assert (
            'Poe => echo "deploying to admin:12345@prod.example.com/app"\n'
            in result.capture
        )
        assert result.stdout == '"deploying to admin:12345@prod.example.com/app"\n'
        assert result.stderr == ""
    else:
        assert (
            "Poe => echo deploying to admin:12345@prod.example.com/app\n"
            in result.capture
        )
        assert result.stdout == "deploying to admin:12345@prod.example.com/app\n"
        assert result.stderr == ""
