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
