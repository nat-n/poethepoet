import os
from pathlib import Path
import sys


def test_global_envfile_and_default(run_poe_subproc, is_windows):
    result = run_poe_subproc("deploy-dev", project="envfile")
    if is_windows:
        # On windows shlex works in non-POSIX mode which results in  quotes
        assert (
            'Poe => poe_test_echo "deploying to admin:12345@dev.example.com:8080"\n'
            in result.capture
        )
        assert result.stdout == '"deploying to admin:12345@dev.example.com:8080"\n'
        assert result.stderr == ""
    else:
        assert (
            "Poe => poe_test_echo deploying to admin:12345@dev.example.com:8080\n"
            in result.capture
        )
        assert result.stdout == "deploying to admin:12345@dev.example.com:8080\n"
        assert result.stderr == ""


def test_task_envfile_and_default(run_poe_subproc, is_windows):
    result = run_poe_subproc("deploy-prod", project="envfile")
    if is_windows:
        assert (
            'Poe => poe_test_echo "deploying to admin:12345@prod.example.com/app"\n'
            in result.capture
        )
        assert result.stdout == '"deploying to admin:12345@prod.example.com/app"\n'
        assert result.stderr == ""
    else:
        assert (
            "Poe => poe_test_echo deploying to admin:12345@prod.example.com/app\n"
            in result.capture
        )
        assert result.stdout == "deploying to admin:12345@prod.example.com/app\n"
        assert result.stderr == ""


def test_multiple_envfiles(run_poe_subproc, projects, is_windows):
    result = run_poe_subproc(
        f'--root={projects["envfile/multiple_envfiles"]}', "show_me_the_vals"
    )

    if is_windows:
        assert (
            'Poe => poe_test_echo "VAL_A-VAL_B-VAL_C-VAL_D-VAL_E-VAL_F!!"\n'
            in result.capture
        )
        assert result.stdout == '"VAL_A-VAL_B-VAL_C-VAL_D-VAL_E-VAL_F!!"\n'
        assert result.stderr == ""
    else:
        assert (
            "Poe => poe_test_echo VAL_A-VAL_B-VAL_C-VAL_D-VAL_E-VAL_F!!\n"
            in result.capture
        )
        assert result.stdout == "VAL_A-VAL_B-VAL_C-VAL_D-VAL_E-VAL_F!!\n"
        assert result.stderr == ""
