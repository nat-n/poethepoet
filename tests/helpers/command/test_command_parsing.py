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


def test_resolve_command_tokens_param_operation_preserves_quotes():
    """
    Test that quotes inside :+ and :- parameter operations are respected,
    preventing incorrect word splitting. (GitHub issue #333)
    """

    # Alternate value with single-quoted argument
    line = parse_poe_cmd("echo pytest ${SKIP:+ -m 'not build'}")[0]
    assert list(resolve_command_tokens([line], {"SKIP": "1"})) == [
        ("echo", False),
        ("pytest", False),
        ("-m", False),
        ("not build", False),
    ]

    # Alternate value not triggered (var unset)
    assert list(resolve_command_tokens([line], {})) == [
        ("echo", False),
        ("pytest", False),
    ]

    # Default value with single-quoted argument
    line = parse_poe_cmd("echo ${X:-'hello world'}")[0]
    assert list(resolve_command_tokens([line], {})) == [
        ("echo", False),
        ("hello world", False),
    ]

    # Default value not triggered (var set)
    assert list(resolve_command_tokens([line], {"X": "val"})) == [
        ("echo", False),
        ("val", False),
    ]

    # Double-quoted argument in operation
    line = parse_poe_cmd("""echo ${X:+"hello world"}""")[0]
    assert list(resolve_command_tokens([line], {"X": "1"})) == [
        ("echo", False),
        ("hello world", False),
    ]

    # Mixed quoted and unquoted parts in operation argument
    line = parse_poe_cmd("echo ${X:+--flag 'a b' --other}")[0]
    assert list(resolve_command_tokens([line], {"X": "1"})) == [
        ("echo", False),
        ("--flag", False),
        ("a b", False),
        ("--other", False),
    ]

    # Quoted part adjacent to surrounding text (no word break)
    line = parse_poe_cmd("echo A${X:+'bar'}B")[0]
    assert list(resolve_command_tokens([line], {"X": "1"})) == [
        ("echo", False),
        ("AbarB", False),
    ]

    # Operation argument with leading/trailing whitespace and quotes
    line = parse_poe_cmd("echo ${X:+ -m 'not build' --verbose}")[0]
    assert list(resolve_command_tokens([line], {"X": "1"})) == [
        ("echo", False),
        ("-m", False),
        ("not build", False),
        ("--verbose", False),
    ]
