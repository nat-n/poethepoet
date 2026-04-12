from poethepoet.helpers.command import parse_poe_cmd, resolve_command_tokens


def test_resolve_command_tokens():
    line = parse_poe_cmd(
        """
        abc${thing1}def *$thing2?
        """
    )[0]

    assert list(resolve_command_tokens([line], {"thing2": ""})) == [
        ("abcdef", False),
        ("*?", True),
    ]

    assert list(
        resolve_command_tokens([line], {"thing1": " space ", "thing2": "s p a c e"})
    ) == [
        ("abc", False),
        ("space", False),
        ("def", False),
        ("*s", True),
        ("p", False),
        ("a", False),
        ("c", False),
        ("e?", True),
    ]

    assert list(
        resolve_command_tokens([line], {"thing1": " space ", "thing2": "s p a c e"})
    ) == [
        ("abc", False),
        ("space", False),
        ("def", False),
        ("*s", True),
        ("p", False),
        ("a", False),
        ("c", False),
        ("e?", True),
    ]

    assert list(
        resolve_command_tokens([line], {"thing1": "x'[!] ]'y", "thing2": "z [foo ? "})
    ) == [
        ("abcx'[!]", True),
        ("]'ydef", False),
        ("*z", True),
        ("[foo", False),
        ("?", True),
        ("?", True),
    ]

    line = parse_poe_cmd(
        """
        "ab$thing1* and ${thing2}? '${thing1}'" '${thing1}' ""
        """
    )[0]

    assert list(resolve_command_tokens([line], {"thing1": r" *\o/", "thing2": ""})) == [
        (r"ab *\o/* and ? ' *\o/'", False),
        ("${thing1}", False),
        ("", False),
    ]

    lines = parse_poe_cmd(
        """
        # comment
        one # comment
        two # comment
        three # comment
        # comment
        """
    )

    assert list(resolve_command_tokens(lines, {})) == [
        ("one", False),
        ("two", False),
        ("three", False),
    ]


def test_resolve_param_operation_preserves_quotes():
    """Regression test for https://github.com/nat-n/poethepoet/issues/333

    Quotes within :+ and :- operation arguments should be preserved so that
    quoted strings remain single tokens after word splitting.
    """
    # Single quotes in :+ alternate value
    line = parse_poe_cmd("echo pytest ${SKIP_BUILD:+ -m 'not build'}")[0]
    assert list(resolve_command_tokens([line], {"SKIP_BUILD": "1"})) == [
        ("echo", False),
        ("pytest", False),
        ("-m", False),
        ("not build", False),
    ]
    # When unset, alternate value is not used
    assert list(resolve_command_tokens([line], {})) == [
        ("echo", False),
        ("pytest", False),
    ]

    # Double quotes in :- default value
    line = parse_poe_cmd('echo ${GREETING:-"hello world"}')[0]
    assert list(resolve_command_tokens([line], {})) == [
        ("echo", False),
        ("hello world", False),
    ]
    # When set, default value is not used
    assert list(resolve_command_tokens([line], {"GREETING": "hi"})) == [
        ("echo", False),
        ("hi", False),
    ]

    # Mixed: unquoted and quoted parts in operation argument
    line = parse_poe_cmd("cmd ${X:+--flag 'a b' --other}")[0]
    assert list(resolve_command_tokens([line], {"X": "1"})) == [
        ("cmd", False),
        ("--flag", False),
        ("a b", False),
        ("--other", False),
    ]
