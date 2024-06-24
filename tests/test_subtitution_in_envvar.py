def test_substitution_in_envvar(run_poe_subproc):
    result = run_poe_subproc("frobnicate", project="substitution_in_envvar")

    assert result.capture == "Poe => ${FILE}\n"
    assert result.stdout == "/foo/bar/baz\n"
    assert result.stderr == ""
