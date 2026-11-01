import pytest


@pytest.fixture
def root_dir(projects):
    return projects["project_refs"]


@pytest.fixture
def project_load_calls(monkeypatch):
    from poethepoet.task import project_ref

    calls = []
    original = project_ref.load_project

    async def counting_load(config_file, io):
        calls.append(config_file)
        return await original(config_file, io)

    monkeypatch.setattr(project_ref, "load_project", counting_load)
    return calls


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


def test_ref_project_env_layering(run_poe):
    result = run_poe("foo-env", project="project_refs")
    assert result.code == 0
    assert result.stdout == (
        "SHARED=from-foo OVERRIDABLE=from-root ROOT_ONLY=root FOO_ONLY=foo "
        "REF_VAR=from-ref\n"
    )


@pytest.mark.parametrize("task", ["foo-env-file", "foo-env-abs"])
def test_ref_project_file_and_absolute_paths(run_poe, task):
    result = run_poe(task, project="project_refs")
    assert result.code == 0
    assert result.stdout == (
        "SHARED=from-foo OVERRIDABLE=from-root ROOT_ONLY=root FOO_ONLY=foo REF_VAR=\n"
    )


def test_ref_project_templated_path_and_extra_args(run_poe):
    result = run_poe("run-in", "foo", "--", "--strict", project="project_refs")
    assert result.code == 0
    assert result.stdout == "foo got --strict\n"


def test_ref_project_paths_are_childs(run_poe, root_dir):
    foo_dir = root_dir / "packages" / "foo"
    result = run_poe("foo-paths", project="project_refs")
    assert result.stdout == f"{foo_dir} {foo_dir} {root_dir}\n"


def test_ref_project_target_uses_resolve_in_child(run_poe):
    result = run_poe("foo-graph", project="project_refs")
    assert result.code == 0
    assert result.stdout == "graph foo-prep\n"


def test_ref_project_uses_child_executor(run_poe, root_dir):
    result = run_poe("bar-hello", project="project_refs")
    assert result.code == 1
    assert (
        "Could not find valid virtualenv at configured location: "
        f"{root_dir / 'packages' / 'bar' / 'missing_venv'}"
    ) in result.capture


def test_ref_project_cli_executor_override_and_lazy_validation(run_poe):
    # bar's invalid 'broken' task must not block running 'hello'
    result = run_poe("-e", "simple", "bar-hello", project="project_refs")
    assert result.code == 0
    assert result.stdout == "hello from bar\n"


def test_ref_project_poe_tasks_file(run_poe):
    result = run_poe("tasksfile-hello", project="project_refs")
    assert result.stdout == "hello from tasksfile\n"


def test_ref_project_self_reference(run_poe):
    result = run_poe("self-show-env", project="project_refs")
    assert result.stdout == "root show-env\n"


def test_ref_project_loaded_once_per_run(run_poe, project_load_calls):
    # dir, config-file and absolute spellings of the same project share one load
    result = run_poe("foo-twice", project="project_refs")
    assert result.code == 0
    assert len(project_load_calls) == 1


@pytest.mark.parametrize("task", ["foo-nomatch-ok", "quiet-nomatch-ok"])
def test_ref_project_ignore_fail_warns_at_ref_verbosity(run_poe, task):
    # The warning belongs to the ref task, so a quiet target project doesn't hide it
    result = run_poe(task, project="project_refs")
    assert result.code == 0
    assert "Warning: Glob pattern '*.nomatch' did not match any files" in (
        result.capture
    )
