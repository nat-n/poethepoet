def test_ref_project_rejects_cwd(run_poe, temp_pyproject):
    project_path = temp_pyproject("""
        [tool.poe.tasks.bad]
        ref = "x"
        project = "sub"
        cwd = "sub"
        """)
    result = run_poe("bad", cwd=project_path)
    assert result.code == 1
    assert (
        "'project' and 'cwd' options cannot be both provided on the same task."
        in result.capture
    )


def test_ref_project_target_not_checked_at_load(run_poe, temp_pyproject):
    project_path = temp_pyproject("""
        [tool.poe.tasks.other]
        cmd = "poe_test_echo ok"

        [tool.poe.tasks.ghost]
        ref = "nope"
        project = "missing"

        [tool.poe.tasks.ghost-capture]
        ref = "nope"
        project = "missing"
        capture_stdout = "out.txt"
        """)
    result = run_poe("other", cwd=project_path)
    assert result.code == 0
    assert result.stdout == "ok\n"
