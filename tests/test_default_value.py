def test_global_envfile_and_default(run_poe_subproc, poe_project_path):
    project_path = poe_project_path.joinpath("tests", "fixtures", "default_value")
    result = run_poe_subproc("test", cwd=project_path)
    assert "Poe => echo !one! !two! !three! !four! !five! !six!\n" in result.capture
    assert result.stdout == "!one! !two! !three! !four! !five! !six!\n"
    assert result.stderr == ""


def test_global_envfile_and_default_with_presets(run_poe_subproc, poe_project_path):
    project_path = poe_project_path.joinpath("tests", "fixtures", "default_value")

    env = {
        "ONE": "111",
        "TWO": "222",
        "THREE": "333",
        "FOUR": "444",
        "FIVE": "555",
        "SIX": "666",
    }

    result = run_poe_subproc("test", cwd=project_path, env=env)
    assert "Poe => echo !one! !two! !three! 444 !five! 666\n" in result.capture
    assert result.stdout == "!one! !two! !three! 444 !five! 666\n"
    assert result.stderr == ""
