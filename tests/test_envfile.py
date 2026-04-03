def test_global_envfile_and_default(run_poe):
    result = run_poe("deploy-dev", project="envfile")
    assert (
        "Poe => poe_test_echo 'deploying to admin:12345@dev.example.com:8080'\n"
        in result.capture
    )
    assert result.stdout == "deploying to admin:12345@dev.example.com:8080\n"
    assert result.stderr == ""


def test_task_envfile_and_default(run_poe):
    result = run_poe("deploy-prod", project="envfile")
    assert (
        "Poe => poe_test_echo 'deploying to admin:12345@prod.example.com/app'\n"
        in result.capture
    )
    assert result.stdout == "deploying to admin:12345@prod.example.com/app\n"
    assert result.stderr == ""


def test_envfile_private_var_filtered_from_subprocess(run_poe, is_windows):
    result = run_poe("show-envfile-vars", project="envfile")
    if not is_windows:
        assert "_secret=hidden" not in result.stdout
    assert "PUBLIC_UNDERSCORE=VISIBLE" in result.stdout
    assert result.stderr == ""


def test_envfile_private_var_inherited_and_filtered(run_poe, is_windows):
    result = run_poe("inherit-envfile-private", project="envfile")
    if not is_windows:
        assert "_secret=hidden" not in result.stdout
    assert "PUBLIC_UNDERSCORE=VISIBLE" in result.stdout
    assert result.stderr == ""


def test_envfile_private_var_inherited_can_be_remapped_public(run_poe):
    result = run_poe("remap-envfile-private", project="envfile")
    stdout_lower = result.stdout.lower()
    assert "public=hidden" in stdout_lower
    assert result.stderr == ""


def test_multiple_envfiles(run_poe, projects):
    result = run_poe(f"-C={projects['envfile/multiple_envfiles']}", "show_me_the_vals")

    assert (
        "Poe => poe_test_echo 'VAL_A-VAL_B-VAL_C-VAL_D-VAL_E-VAL_F!!'\n"
        in result.capture
    )
    assert result.stdout == "VAL_A-VAL_B-VAL_C-VAL_D-VAL_E-VAL_F!!\n"
    assert result.stderr == ""


def test_trying_to_load_nonexistent_envfiles(run_poe, projects):
    result = run_poe(
        f"-C={projects['envfile/multiple_envfiles']}", "handle_disappointment"
    )

    assert "Poe => poe_test_echo OK\n" in result.capture
    assert "Warning: Poe failed to locate envfile at" in result.capture
    assert "not-real.env" in result.capture
    assert "imaginary.env" in result.capture
    assert "nothingness.env" not in result.capture
    assert "lies.env" not in result.capture
    assert result.stdout == "OK\n"
    assert result.stderr == ""
