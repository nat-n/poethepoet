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


def test_resolve_alternate_value_preserves_quotes():
    """
    Quoted content inside :+ and :- operators should not be word-split.
    See https://github.com/nat-n/poethepoet/issues/333

    Each case is verified against bash behavior. Cases already covered by
    integration tests in test_cmd_param_expansion.py are not repeated here.
    """
    # Default value not applied when var is set
    line = parse_poe_cmd("echo ${FLAG:- -m 'not build'}")[0]
    assert list(resolve_command_tokens([line], {"FLAG": "yes"})) == [
        ("echo", False),
        ("yes", False),
    ]

    # Expansion embedded in a word — leading/trailing text joins adjacent tokens
    # bash: printf '[%s]\n' x${F:+ -m 'not build'}y → [x] [-m] [not buildy]
    line = parse_poe_cmd("x${FLAG:+ -m 'not build'}y")[0]
    assert list(resolve_command_tokens([line], {"FLAG": "yes"})) == [
        ("x", False),
        ("-m", False),
        ("not buildy", False),
    ]

    # Nested expansion in alternate value — inner value is word-split
    # bash: F=y O="hello world"; printf '[%s]\n' ${F:+ $O} → [hello] [world]
    line = parse_poe_cmd("${FLAG:+ $OTHER}")[0]
    assert list(
        resolve_command_tokens([line], {"FLAG": "y", "OTHER": "hello world"})
    ) == [
        ("hello", False),
        ("world", False),
    ]

    # Outer double quotes suppress word splitting of nested expansion
    # bash: F=y O="hello world"; printf '[%s]\n' "${F:+ $O}" → [ hello world]
    line = parse_poe_cmd('"${FLAG:+ $OTHER}"')[0]
    assert list(
        resolve_command_tokens([line], {"FLAG": "y", "OTHER": "hello world"})
    ) == [
        (" hello world", False),
    ]

    # Nested operations: alternate value containing default value with quotes
    # bash: F=y; printf '[%s]\n' ${F:+${UNSET:-'hello world'}} → [hello world]
    line = parse_poe_cmd("${FLAG:+${UNSET:-'hello world'}}")[0]
    assert list(resolve_command_tokens([line], {"FLAG": "y"})) == [
        ("hello world", False),
    ]

    # Empty alternate value produces nothing
    # bash: F=y; printf '[%s]\n' A${F:+}B → [AB]
    line = parse_poe_cmd("A${FLAG:+}B")[0]
    assert list(resolve_command_tokens([line], {"FLAG": "y"})) == [
        ("AB", False),
    ]
