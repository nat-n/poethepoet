def test_run_poe_merges_env_and_scrubs_inherited_poe_vars(
    run_poe, temp_pyproject, monkeypatch
):
    project_path = temp_pyproject(
        """
        [tool.poe.tasks.show-env]
        cmd = "poe_test_echo ${PARENT_ONLY} ${CHILD_ONLY} ${POE_CWD}"
        capture_stdout = "show-env.txt"
        """
    )
    monkeypatch.setenv("PARENT_ONLY", "parent")
    monkeypatch.setenv("POE_CWD", "/not-the-project")

    result = run_poe("show-env", cwd=project_path, env={"CHILD_ONLY": "child"})

    assert result.code == 0
    assert (
        project_path / "show-env.txt"
    ).read_text() == f"parent child {project_path}\n"
    assert result.stderr == ""


def test_run_poe_env_can_set_project_dir(run_poe, temp_pyproject, monkeypatch):
    project_path = temp_pyproject(
        """
        [tool.poe.tasks.hello]
        cmd = "poe_test_echo hello from env project dir"
        capture_stdout = "hello.txt"
        """
    )
    monkeypatch.setenv("POE_PROJECT_DIR", str(project_path.parent / "wrong-project"))

    result = run_poe("hello", cwd=".", env={"POE_PROJECT_DIR": str(project_path)})

    assert result.code == 0
    assert (project_path / "hello.txt").read_text() == "hello from env project dir\n"
    assert result.stderr == ""
