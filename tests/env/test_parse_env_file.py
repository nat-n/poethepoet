import pytest

from poethepoet.env.parse import parse_env_file

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
        DOUBLE_QUOTED_WORD_ESC="some\
        thing"
        SINGLE_QUOTED_WORD_ESC='some\
        thing'
        """,
        {
            "WORD": "something",
            "DOUBLE_QUOTED_WORD": "some\n        thing",
            "SINGLE_QUOTED_WORD": "some\n        thing",
            "DOUBLE_QUOTED_WORD_ESC": "some        thing",
            "SINGLE_QUOTED_WORD_ESC": "some        thing",
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
    ; FOO=BAR;BAR=FOO\\;! ;
    ;
    BAZ="2;'2"#;
    \tQUX=3\t;
    """,
        {"FOO": "BAR", "BAR": "FOO;!", "BAZ": "2;'2#", "QUX": "3"},
    ),
    (
        r"""
    # with extra backslashes
    FOO=a\\\ b
    BAR='a\\\ b'
    BAZ="a\\\ b"
    """,
        {"FOO": r"a\ b", "BAR": r"a\\\ b", "BAZ": r"a\\ b"},
    ),
    (  # a value with many parts and some empty vars
        r"""FOO=a\\\ b'a\\\ b'"a\\\ b"#"#"'\'' ;'#; #\t
    BAR=
    BAZ= # still empty
    QUX=
    WUT='a'"b"\
c """,
        {
            "FOO": r"a\ ba\\\ ba\\ b##\ ;#",
            "BAR": "",
            "BAZ": "",
            "QUX": "",
            "WUT": "abc",
        },
    ),
    # export keyword is allowed
    (
        """export answer=42
        export              \t               question=undefined
        export\tdinner=chicken
        """,
        {"answer": "42", "question": "undefined", "dinner": "chicken"},
    ),
    # handling escapes
    (
        """
        ESCAPED_DQUOTE=\\"
        ESCAPED_DQUOTE_DQUOTES='\\"'
        ESCAPED_DQUOTE_SQUOTES="\\""
        ESCAPED_NEWLINE=a\\
b;
        ESCAPED_NEWLINE_DQUOTES='\\"'
        ESCAPED_NEWLINE_SQUOTES="\\""
        """,
        {
            "ESCAPED_DQUOTE": '"',
            "ESCAPED_DQUOTE_DQUOTES": '\\"',
            "ESCAPED_DQUOTE_SQUOTES": '"',
            "ESCAPED_NEWLINE": "ab",
            "ESCAPED_NEWLINE_DQUOTES": '\\"',
            "ESCAPED_NEWLINE_SQUOTES": '"',
        },
    ),
    # comments
    (
        r"""# at start
        EX1=BAR#NOT_COMMENT
        EX2="BAR#NOT_COMMENT"
        EX3='BAR#NOT_COMMENT'
        EX4=BAR\ #NOT_COMMENT
        EX5="BAR #NOT_COMMENT"
        EX6='BAR #NOT_COMMENT'
        EX7=BAR\
#NOT_COMMENT
        EX8=BAR #COMMENT
        EX9=BAR\  #COMMENT
        EX10=BAR; #COMMENT
        EX11=BAR;#COMMENT
        EX12=BAR\;;#COMMENT
        EX13=BAR\
        #COMMENT'
        #COMMENT'
        """,
        {
            "EX1": "BAR#NOT_COMMENT",
            "EX2": "BAR#NOT_COMMENT",
            "EX3": "BAR#NOT_COMMENT",
            "EX4": "BAR #NOT_COMMENT",
            "EX5": "BAR #NOT_COMMENT",
            "EX6": "BAR #NOT_COMMENT",
            "EX7": "BAR#NOT_COMMENT",
            "EX8": "BAR",
            "EX9": "BAR ",
            "EX10": "BAR",
            "EX11": "BAR",
            "EX12": "BAR;",
            "EX13": "BAR",
        },
    ),
    (
        r"""
        EQL=="="
        FOO=\\x\n\x77
        FOOSQ='\\x\n\x77'
        FOODQ="\\x\n\x77"
        """,
        {"EQL": "==", "FOO": "\\xnx77", "FOOSQ": r"\\x\n\x77", "FOODQ": "\\x\\n\\x77"},
    ),
    (
        r"""
        FOO=first
        FOO=second
        """,
        {"FOO": "second"},
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
    r"""foo='\'' """,
    r"""foo="\" """,
]


@pytest.mark.parametrize("example", valid_examples)
def test_parse_valid_env_files(example):
    assert parse_env_file(example[0]) == example[1]


@pytest.mark.parametrize("example", invalid_examples)
def test_parse_invalid_env_files(example):
    # ruff: noqa: PT011
    with pytest.raises(ValueError):
        parse_env_file(example)
