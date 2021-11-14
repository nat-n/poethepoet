from poethepoet.envfile import parse_env_file
import pytest

valid_examples = [
    (
        """
    # empty
    """,
        {},
    ),
    (
        """
        # single word values
        WORD=something
        WORD_WITH_HASH=some#thing
        NUMBER=0
        EMOJI=😃😃
        DOUBLE_QUOTED_WORD="something"
        SINGLE_QUOTED_WORD='something'
        """,
        {
            "WORD": "something",
            "WORD_WITH_HASH": "some#thing",
            "NUMBER": "0",
            "EMOJI": "😃😃",
            "DOUBLE_QUOTED_WORD": "something",
            "SINGLE_QUOTED_WORD": "something",
        },
    ),
    (
        """
        # multiword values
        WORD=some\\ thing                   # and trailing comments
        DOUBLE_QUOTED_WORD="some thing"
        SINGLE_QUOTED_WORD='some thing'
        """,
        {
            "WORD": r"some thing",
            "DOUBLE_QUOTED_WORD": "some thing",
            "SINGLE_QUOTED_WORD": "some thing",
        },
    ),
    (
        """
        # values with line breaks
        WORD=some\\
thing
        DOUBLE_QUOTED_WORD="some
        thing"
        SINGLE_QUOTED_WORD='some
        thing'
        """,
        {
            "WORD": "some\nthing",
            "DOUBLE_QUOTED_WORD": "some\n        thing",
            "SINGLE_QUOTED_WORD": "some\n        thing",
        },
    ),
    (
        """
    # without linebreak between vars
    FOO=BAR BAR=FOO
    """,
        {"FOO": "BAR", "BAR": "FOO"},
    ),
    (
        """
    # with semicolons
    ; FOO=BAR;BAR=FOO ;
    ;
    BAZ="2;'2"#;
    \tQUX=3\t;
    """,
        {"FOO": "BAR", "BAR": "FOO", "BAZ": "2;'2#", "QUX": "3"},
    ),
    (
        r"""
    # with extra backslashes
    FOO=a\\\ b
    BAR='a\\\ b'
    BAZ="a\\\ b"
    """,
        {"FOO": r"a\ b", "BAR": r"a\\\ b", "BAZ": r"a\ b"},
    ),
    (  # a value with many parts and some empty vars
        r"""FOO=a\\\ b'a\\\ b'"a\\\ b"#"#"'\'' ;'#;\t
    BAR=
    BAZ= # still empty
    QUX=""",
        {"FOO": r"a\ ba\\\ ba\ b##\ ;#", "BAR": "", "BAZ": "", "QUX": ""},
    ),
    # export keyword is allowed
    (
        """export answer=42
        export              \t               question=undefined
        export\tdinner=chicken
        """,
        {"answer": "42", "question": "undefined", "dinner": "chicken"},
    ),
]


invalid_examples = [
    "foo = bar",
    "foo =bar",
    "foo= bar",
    "foo\t=\tbar",
    "foo\t=bar",
    "foo=\tbar",
    "foo= 'bar",
    'foo= "bar"',
    "foo",
    "foo;",
    "8oo=bar",
    "foo@=bar",
    '"foo@"=bar',
    "'foo@'=bar",
    r"foo\=bar",
    r"foo\==bar",
    r"export;foo=bar",
    r"export\nfoo=bar",
]


@pytest.mark.parametrize("example", valid_examples)
def test_parse_valid_env_files(example):
    assert parse_env_file(example[0]) == example[1]


@pytest.mark.parametrize("example", invalid_examples)
def test_parse_invalid_env_files(example):
    with pytest.raises(ValueError):
        parse_env_file(example)
