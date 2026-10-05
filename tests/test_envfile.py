from pathlib import Path


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


def test_mixed_list_of_envfiles(run_poe, projects):
    """
    A list of envfiles may mix plain paths with tables of expected/optional paths.
    """
    result = run_poe(f"-C={projects['envfile/mixed_envfiles']}", "show_me_the_vals")

    assert result.stdout == "VAL_A-VAL_B-NOT_C-VAL_D-VAL_E\n"
    assert "Warning" not in result.capture
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


# ---------------------------------------------------------------------------
# Parameter expansion in envfile values
# ---------------------------------------------------------------------------


def test_envfile_basic_param_expansion(temp_pyproject, run_poe, tmp_path):
    """
    Basic ${VAR} expansion within an envfile: later vars reference earlier ones.
    """
    envfile = tmp_path / "test.env"
    envfile.write_text("BASE=/opt\nFULL=${BASE}/app\n")
    project_path = temp_pyproject(f"""
        [tool.poe]
        envfile = "{envfile.as_posix()}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${{FULL}}"
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "/opt/app\n"


def test_envfile_default_value_operator(temp_pyproject, run_poe, tmp_path):
    """
    ${VAR:-default} in an envfile should use default when VAR is unset.
    """
    envfile = tmp_path / "test.env"
    envfile.write_text("GREETING=${NAME:-world}\n")
    project_path = temp_pyproject(f"""
        [tool.poe]
        envfile = "{envfile.as_posix()}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${{GREETING}}"
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "world\n"


def test_envfile_default_value_overridden(temp_pyproject, run_poe, tmp_path):
    """
    ${VAR:-default} in an envfile should use VAR when it was set earlier.
    """
    envfile = tmp_path / "test.env"
    envfile.write_text("NAME=alice\nGREETING=${NAME:-world}\n")
    project_path = temp_pyproject(f"""
        [tool.poe]
        envfile = "{envfile.as_posix()}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${{GREETING}}"
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "alice\n"


def test_envfile_alternate_value_operator(temp_pyproject, run_poe, tmp_path):
    """
    ${VAR:+alternate} in an envfile should use alternate when VAR is set.
    """
    envfile = tmp_path / "test.env"
    envfile.write_text("DEBUG=1\nFLAG=${DEBUG:+--debug}\n")
    project_path = temp_pyproject(f"""
        [tool.poe]
        envfile = "{envfile.as_posix()}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${{FLAG}}"
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "--debug\n"


def test_envfile_alternate_value_unset(temp_pyproject, run_poe, tmp_path):
    """
    ${VAR:+alternate} in an envfile should be empty when VAR is unset.
    """
    envfile = tmp_path / "test.env"
    envfile.write_text("FLAG=${DEBUG:+--debug}\n")
    project_path = temp_pyproject(f"""
        [tool.poe]
        envfile = "{envfile.as_posix()}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo flag=${{FLAG}}"
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "flag=\n"


def test_envfile_expansion_in_double_quotes(temp_pyproject, run_poe, tmp_path):
    """
    ${VAR} expansion inside double-quoted envfile values.
    """
    envfile = tmp_path / "test.env"
    envfile.write_text('HOST=example.com\nURL="https://${HOST}/api"\n')
    project_path = temp_pyproject(f"""
        [tool.poe]
        envfile = "{envfile.as_posix()}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${{URL}}"
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "https://example.com/api\n"


def test_envfile_no_expansion_in_single_quotes(temp_pyproject, run_poe, tmp_path):
    """
    ${VAR} inside single-quoted envfile values should NOT be expanded.
    """
    envfile = tmp_path / "test.env"
    envfile.write_text("HOST=example.com\nLITERAL='${HOST}'\n")
    project_path = temp_pyproject(f"""
        [tool.poe]
        envfile = "{envfile.as_posix()}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${{LITERAL}}"
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "${HOST}\n"


def test_envfile_nested_default_value(temp_pyproject, run_poe, tmp_path):
    """
    Nested :- operators in envfile: ${A:-${B:-fallback}}.
    """
    envfile = tmp_path / "test.env"
    envfile.write_text("RESULT=${PRIMARY:-${SECONDARY:-fallback}}\n")
    project_path = temp_pyproject(f"""
        [tool.poe]
        envfile = "{envfile.as_posix()}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${{RESULT}}"
        """)
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "fallback\n"


def test_envfile_with_utf8_bom(temp_pyproject, run_poe, tmp_path):
    """
    A UTF-8 byte order mark at the start of an envfile (as written by some Windows
    editors) is ignored.
    """
    envfile = tmp_path / "bom.env"
    envfile.write_bytes(b"\xef\xbb\xbfFIRST=one\nSECOND=two\n")
    project_path = temp_pyproject(
        f"""
        [tool.poe]
        envfile = "{envfile.as_posix()}"

        [tool.poe.tasks.show]
        cmd = "poe_test_echo ${{FIRST}}-${{SECOND}}"
        """
    )
    result = run_poe("show", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "one-two\n"


ENVFILE_ERROR_PROJECT = """
    [tool.poe.tasks.show]
    cmd = "poe_test_echo ${{A}}"
    envfile = "{envfile}"
    """


def test_envfile_syntax_error_reports_line(temp_pyproject, run_poe, tmp_path):
    envfile = tmp_path / "bad.env"
    envfile.write_text("A=1\nB=2\nC 3\n")
    project_path = temp_pyproject(
        ENVFILE_ERROR_PROJECT.format(envfile=envfile.as_posix())
    )
    result = run_poe("show", cwd=project_path)
    assert result.code == 1
    assert "Syntax error in referenced envfile" in result.capture
    assert "Expected '=' after variable name 'C' (near line 3" in result.capture
    assert "Traceback" not in result.capture


def test_envfile_not_utf8(temp_pyproject, run_poe, tmp_path):
    envfile = tmp_path / "latin1.env"
    envfile.write_bytes(b"A=caf\xe9\n")
    project_path = temp_pyproject(
        ENVFILE_ERROR_PROJECT.format(envfile=envfile.as_posix())
    )
    result = run_poe("show", cwd=project_path)
    assert result.code == 1
    assert (
        f"Envfile at {str(envfile)!r} could not be decoded as UTF-8" in result.capture
    )
    assert "Traceback" not in result.capture


def test_envfile_unreadable(temp_pyproject, run_poe, tmp_path, monkeypatch):
    envfile = tmp_path / "unreadable.env"
    envfile.write_text("A=1\n")
    project_path = temp_pyproject(
        ENVFILE_ERROR_PROJECT.format(envfile=envfile.as_posix())
    )
    original_open = Path.open

    def guarded_open(self, *args, **kwargs):
        if self.name == "unreadable.env":
            raise PermissionError(13, "Permission denied")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    result = run_poe("show", cwd=project_path)
    assert result.code == 1
    assert (
        f"Failed to read envfile at {str(envfile)!r}: Permission denied"
        in result.capture
    )
    assert "Traceback" not in result.capture
