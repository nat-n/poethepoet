def test_global_envfile_and_default(run_poe_subproc):
    result = run_poe_subproc("test", project="default_value")
    assert (
        "Poe => poe_test_echo '!one!' '!two!' '!three!' '!four!' '!five!' '!six!'\n"
        in result.capture
    )
    assert result.stdout == "!one! !two! !three! !four! !five! !six!\n"
    assert result.stderr == ""


def test_global_envfile_and_default_with_presets(run_poe_subproc):
    env = {
        "ONE": "111",
        "TWO": "222",
        "THREE": "333",
        "FOUR": "444",
        "FIVE": "555",
        "SIX": "666",
    }

    result = run_poe_subproc("test", project="default_value", env=env)
    assert (
        "Poe => poe_test_echo '!one!' '!two!' '!three!' 444 '!five!' 666\n"
        in result.capture
    )
    assert result.stdout == "!one! !two! !three! 444 !five! 666\n"
    assert result.stderr == ""
