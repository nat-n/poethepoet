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
        r"""
        # values with line breaks
        WORD=some\
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
            # backslash-newline is a line continuation in double quotes...
            "DOUBLE_QUOTED_WORD_ESC": "some        thing",
            # ...but kept literally in single quotes
            "SINGLE_QUOTED_WORD_ESC": "some\\\n        thing",
        },
    ),
    (
        # whitespace within unquoted value is preserved; only \n terminates
        "FOO=BAR BAZ=QUX\n",
        {"FOO": "BAR BAZ=QUX"},
    ),
    (
        # semicolons are regular characters in unquoted and quoted values
        'FOO=bar;baz\nBAR="qux;quux"\n',
        {"FOO": "bar;baz", "BAR": "qux;quux"},
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
            "FOO": r"a\ ba\\\ ba\\ b##\ ;#;",
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
    # names that share a prefix with the export keyword are not scrambled
    (
        "e=1\nex=2\nexp=3\nexpor=4\nexit_code=5\nexpected=6\n",
        {
            "e": "1",
            "ex": "2",
            "exp": "3",
            "expor": "4",
            "exit_code": "5",
            "expected": "6",
        },
    ),
    # names that start with the export keyword are still names
    (
        "exports=1\nexport=2\nexporter=3\nexport_4=4\nexport export5=5\n",
        {
            "exports": "1",
            "export": "2",
            "exporter": "3",
            "export_4": "4",
            "export5": "5",
        },
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
            "ESCAPED_NEWLINE": "ab;",
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
            "EX10": "BAR;",
            "EX11": "BAR;#COMMENT",
            "EX12": "BAR;;#COMMENT",
            "EX13": "BAR",
        },
    ),
    # escaped whitespace is literal, so isn't stripped as trailing whitespace
    (
        "TRAILING_SPACE=foo\\ \nTRAILING_TAB=foo\\\t\nTWO=a\\ \\  \nMIXED=x\\\t #c\n",
        {
            "TRAILING_SPACE": "foo ",
            "TRAILING_TAB": "foo\t",
            "TWO": "a  ",
            "MIXED": "x\t",
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


# ---------------------------------------------------------------------------
# Parameter expansion in envfile values
# ---------------------------------------------------------------------------

param_expansion_examples = [
    # Basic forward reference
    (
        "BASE=/opt\nPATH_VAR=${BASE}/bin\n",
        {"BASE": "/opt", "PATH_VAR": "/opt/bin"},
    ),
    # Default value operator
    (
        "RESULT=${MISSING:-fallback}\n",
        {"RESULT": "fallback"},
    ),
    # Default value with existing var
    (
        "NAME=alice\nGREETING=${NAME:-world}\n",
        {"NAME": "alice", "GREETING": "alice"},
    ),
    # Alternate value operator - var set
    (
        "DEBUG=1\nFLAG=${DEBUG:+--debug}\n",
        {"DEBUG": "1", "FLAG": "--debug"},
    ),
    # Alternate value operator - var unset
    (
        "FLAG=${DEBUG:+--debug}\n",
        {"FLAG": ""},
    ),
    # Nested default
    (
        "VAL=${A:-${B:-deep}}\n",
        {"VAL": "deep"},
    ),
    # Expansion in double quotes
    (
        'HOST=example.com\nURL="https://${HOST}"\n',
        {"HOST": "example.com", "URL": "https://example.com"},
    ),
    # Default with empty argument
    (
        "RESULT=${MISSING:-}\n",
        {"RESULT": ""},
    ),
]


@pytest.mark.parametrize("example", param_expansion_examples)
def test_parse_env_file_param_expansion(example):
    assert parse_env_file(example[0]) == example[1]


literal_dollar_examples = [
    # trailing $
    ('UQ=100$\nDQ="100$"\n', {"UQ": "100$", "DQ": "100$"}),
    # $ followed by punctuation
    ('UQ=x$%y\nDQ="x$%y"\n', {"UQ": "x$%y", "DQ": "x$%y"}),
    ('UQ=$/tmp\nDQ="$/tmp"\n', {"UQ": "$/tmp", "DQ": "$/tmp"}),
    # $$ and other special parameters that refer to the state of a shell are kept
    ('UQ=pa$$word\nDQ="pa$$word"\n', {"UQ": "pa$$word", "DQ": "pa$$word"}),
    (
        'UQ=$?$!$#$-$0\nDQ="$?$!$#$-$0"\n',
        {"UQ": "$?$!$#$-$0", "DQ": "$?$!$#$-$0"},
    ),
    # $ surrounded by whitespace
    ('UQ=a $ b\nDQ="a $ b"\n', {"UQ": "a $ b", "DQ": "a $ b"}),
    # $ followed by a quote or a comment
    ("UQ=a$'b'\n", {"UQ": "a$b"}),
    ("UQ=a$#b\nUQ2=a$ #comment\n", {"UQ": "a$#b", "UQ2": "a$"}),
    # $ that isn't an expansion mixed with ones that are
    ("X=1\nUQ=$-$X-$\n", {"X": "1", "UQ": "$-1-$"}),
]


@pytest.mark.parametrize(("content", "expected"), literal_dollar_examples)
def test_parse_env_file_literal_dollar(content, expected):
    """
    A $ that doesn't start a parameter expansion is kept literally in unquoted
    values, consistent with double-quoted values.
    """
    assert parse_env_file(content) == expected


positional_param_examples = [
    # positional parameters aren't expansions in envfiles, so are kept literally
    ('UQ=abc$1def\nDQ="abc$1def"\n', {"UQ": "abc$1def", "DQ": "abc$1def"}),
    ('UQ=a$10b\nDQ="a$9$10b"\n', {"UQ": "a$10b", "DQ": "a$9$10b"}),
    ('UQ=a$@b$*c\nDQ="a$@b$*c"\n', {"UQ": "a$@b$*c", "DQ": "a$@b$*c"}),
    # also when nested in another expansion
    ('UQ=${MISSING:-x$1y}\nDQ="${MISSING:-x$1y}"\n', {"UQ": "x$1y", "DQ": "x$1y"}),
    # e.g. bcrypt hashes keep their $<digit> parts
    ("HASH=$2b$12\n", {"HASH": "$2b$12"}),
]


@pytest.mark.parametrize(("content", "expected"), positional_param_examples)
def test_parse_env_file_positional_params(content, expected):
    """
    $1 to $9, $@ and $* are kept literally, as only a $ followed by a name or { starts
    an expansion, even if the base env has a variable of that name.
    """
    assert parse_env_file(content, base_env={"1": "one", "@": "at"}) == expected


def test_parse_env_file_no_expansion_in_single_quotes():
    """
    Single-quoted values should NOT have parameter expansion applied.
    """
    assert parse_env_file("HOST=example.com\nLIT='${HOST}'\n") == {
        "HOST": "example.com",
        "LIT": "${HOST}",
    }


# ---------------------------------------------------------------------------
# base_env: host / task-env vars are visible during expansion
# ---------------------------------------------------------------------------

base_env_examples = [
    # host var from base_env is visible
    (
        "URL=https://${HOST}/api\n",
        {"HOST": "example.com"},
        {"URL": "https://example.com/api"},
    ),
    # in-file var takes precedence over base_env
    (
        "HOST=override\nURL=https://${HOST}\n",
        {"HOST": "base"},
        {"HOST": "override", "URL": "https://override"},
    ),
    # base_env var used with default operator
    (
        "GREETING=${NAME:-stranger}\n",
        {"NAME": "alice"},
        {"GREETING": "alice"},
    ),
    # base_env=None behaves like empty env (no regression)
    (
        "FOO=bar\n",
        None,
        {"FOO": "bar"},
    ),
    # alternate operator uses base_env var
    (
        "FLAG=${DEBUG:+--debug}\n",
        {"DEBUG": "1"},
        {"FLAG": "--debug"},
    ),
]


@pytest.mark.parametrize(("content", "base_env", "expected"), base_env_examples)
def test_parse_env_file_with_base_env(content, base_env, expected):
    assert parse_env_file(content, base_env) == expected


def test_parse_env_file_ignores_leading_utf8_bom():
    assert parse_env_file("\ufeffA=1\nB=2\n") == {"A": "1", "B": "2"}


@pytest.mark.parametrize(
    ("content", "location"),
    [
        # errors at the end of input point at the end of the last line, whether or
        # not the file ends with a newline
        ('A=1\nB="x\n', "near line 2, position 5"),
        ('A=1\nB="x', "near line 2, position 5"),
        ("A=1\nB=2\nC 3\n", "near line 3, position 1"),
        # errors at the start of a line point at that line, not the one before
        ("A=1\n=2\n", "near line 2, position 1"),
        ("A=1\n\n\n9=2\n", "near line 4, position 1"),
    ],
)
def test_parse_env_file_error_location(content, location):
    with pytest.raises(ValueError, match=location):
        parse_env_file(content)
