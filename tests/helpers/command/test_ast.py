from io import StringIO

import pytest

from poethepoet.helpers.command import parse_poe_cmd
from poethepoet.helpers.command.ast import Glob, PythonGlob, Script
from poethepoet.helpers.command.ast_core import ParseConfig, ParseCursor, ParseError


def test_parse_comments():
    tree = parse_poe_cmd(
        """# 1
            2 3  # 4 ; 5

            # 6 # 7
            none""",
        config=ParseConfig(),
    )
    print(tree.pretty())
    assert len(tree.lines) == 4
    assert tree.lines[0].comment == " 1"
    assert tree.lines[1] == ((("2",),), (("3",),), " 4 ; 5")
    assert tree.lines[1].words == ((("2",),), (("3",),))
    assert tree.lines[1].comment == " 4 ; 5"
    assert tree.lines[2].comment == " 6 # 7"
    assert tree.lines[3].words == ((("none",),),)
    assert tree.lines[3].comment == ""


def test_parse_params():
    tree = parse_poe_cmd(
        """
        $x${y}$ z
        $x ${y} $ z
        a$x? a${y}b a$? $z
        "$x${y}$ z"
        "$x ${y} $ z"
        "a$x? a${y}b a$? $z"
        '$x${y}$ z'
        '$x ${y} $ z'
        'a$x? a${y}b a$? $z'
        $xx1${yy2}$ z
        $xx1 ${yy2} $ z
        a$xx1? a${yy2}b a$? $z
        "$xx1${yy2}$ z"
        "$xx1 ${yy2} $ z"
        "a$xx1? a${yy2}b a$? $z"
        """,
        config=ParseConfig(),
    )
    print(tree.pretty())
    assert len(tree.lines) == 15
    assert str(tree[0][0][0][0]) == "x"
    assert tree[0][0][0][0].param_name == "x"
    assert tree.lines[0] == (
        (
            (
                "x",
                "y",
                "$",
            ),
        ),
        (("z",),),
    )
    assert tree.lines[1] == (
        (("x",),),
        (("y",),),
        (("$",),),
        (("z",),),
    )
    assert tree.lines[2] == (
        (("a", "x", "?"),),
        (("a", "y", "b"),),
        (("a", "$", "?"),),
        (("z",),),
    )
    assert tree.lines[3] == ((("x", "y", "$ z"),),)
    assert tree.lines[4] == ((("x", " ", "y", " ", "$ z"),),)
    assert tree.lines[5] == ((("a", "x", "? a", "y", "b a", "$? ", "z"),),)
    assert tree.lines[6] == ((("$x${y}$ z",),),)
    assert tree.lines[7] == ((("$x ${y} $ z",),),)
    assert tree.lines[8] == ((("a$x? a${y}b a$? $z",),),)
    assert tree.lines[9] == (
        (
            (
                "xx1",
                "yy2",
                "$",
            ),
        ),
        (("z",),),
    )
    assert tree.lines[10] == (
        (("xx1",),),
        (("yy2",),),
        (("$",),),
        (("z",),),
    )
    assert tree.lines[11] == (
        (("a", "xx1", "?"),),
        (("a", "yy2", "b"),),
        (("a", "$", "?"),),
        (("z",),),
    )
    assert tree.lines[12] == ((("xx1", "yy2", "$ z"),),)
    assert tree.lines[13] == ((("xx1", " ", "yy2", " ", "$ z"),),)
    assert tree.lines[14] == ((("a", "xx1", "? a", "yy2", "b a", "$? ", "z"),),)


def test_parse_param_operators():
    tree = parse_poe_cmd(
        """
        0${x}B
        1${x:+foo}B
        2${x:-bar}B
        3${x:+$foo1}B
        4${x:-a${bar2}b}B
        5${x:- a ${bar} b }B
        6${x:- a ${bar:+ $incepted + 1'"'"';#" } b }B
        7${x:++}B
        8${x:-$}B
        9${x:- }B
        10${x:-}B
        11${x:-(#);?[t]*.ok}B
        12${x:-?[t]*.ok}B
        13${x:-
        split\\  \\ \
        lines
        '  '
        !
        }B
        """,
        config=ParseConfig(),
    )
    print(tree.pretty())
    assert len(tree.lines) == 14
    assert tree.lines[0].words[0].segments[0] == ("0", "x", "B")
    assert tree.lines[1].words[0].segments[0] == (
        "1",
        (
            "x",
            (
                ":+",
                (("foo",),),
            ),
        ),
        "B",
    )
    assert tree.lines[2].words[0].segments[0] == (
        "2",
        (
            "x",
            (
                ":-",
                (("bar",),),
            ),
        ),
        "B",
    )
    assert tree.lines[3].words[0].segments[0] == (
        "3",
        (
            "x",
            (
                ":+",
                ((("foo1",),),),
            ),
        ),
        "B",
    )
    assert tree.lines[4].words[0].segments[0] == (
        "4",
        (
            "x",
            (
                ":-",
                (("a", ("bar2",), "b"),),
            ),
        ),
        "B",
    )
    assert tree.lines[5].words[0].segments[0] == (
        "5",
        (
            "x",
            (
                ":-",
                ((" ", "a", " ", ("bar",), " ", "b", " "),),
            ),
        ),
        "B",
    )
    assert tree.lines[6].words[0].segments[0] == (
        "6",
        (
            "x",
            (
                ":-",
                (
                    (
                        " ",
                        "a",
                        " ",
                        (
                            "bar",
                            (
                                ":+",
                                (
                                    (" ", ("incepted",), " ", "+", " ", "1"),
                                    ('"',),
                                    ("';#",),
                                    (" ",),
                                ),
                            ),
                        ),
                        " ",
                        "b",
                        " ",
                    ),
                ),
            ),
        ),
        "B",
    )
    assert tree.lines[7].words[0].segments[0] == (
        "7",
        (
            "x",
            (
                ":+",
                (("+",),),
            ),
        ),
        "B",
    )
    assert tree.lines[8].words[0].segments[0] == (
        "8",
        (
            "x",
            (
                ":-",
                (("$",),),
            ),
        ),
        "B",
    )
    assert tree.lines[9].words[0].segments[0] == (
        "9",
        (
            "x",
            (
                ":-",
                ((" ",),),
            ),
        ),
        "B",
    )
    assert tree.lines[10].words[0].segments[0] == (
        "10",
        (
            "x",
            (":-", tuple()),
        ),
        "B",
    )
    assert tree.lines[11].words[0].segments[0] == (
        "11",
        (
            "x",
            (":-", (("(#);?[t]*.ok",),)),
        ),
        "B",
    )
    assert tree.lines[12].words[0].segments[0] == (
        "12",
        (
            "x",
            (":-", (("?[t]*.ok",),)),
        ),
        "B",
    )
    assert tree.lines[13].words[0].segments[0] == (
        "13",
        (
            "x",
            (
                ":-",
                (
                    (" ", "split ", " ", " ", " ", "lines", " "),
                    ("  ",),
                    (" ", "!", " "),
                ),
            ),
        ),
        "B",
    )


def test_invalid_param_expansion():
    with pytest.raises(ParseError) as excinfo:
        parse_poe_cmd("""${}""", config=ParseConfig())
    assert excinfo.value.args[0] == "Bad substitution: ${}"

    with pytest.raises(ParseError) as excinfo:
        parse_poe_cmd("""${ x }""", config=ParseConfig())
    assert (
        excinfo.value.args[0]
        == "Bad substitution: Illegal first character in parameter name ' '"
    )

    with pytest.raises(ParseError) as excinfo:
        parse_poe_cmd("""${!x }""", config=ParseConfig())
    assert (
        excinfo.value.args[0]
        == "Bad substitution: Illegal first character in parameter name '!'"
    )

    with pytest.raises(ParseError) as excinfo:
        parse_poe_cmd("""${x }""", config=ParseConfig())
    assert (
        excinfo.value.args[0]
        == "Bad substitution: Illegal character in parameter name ' '"
    )

    with pytest.raises(ParseError) as excinfo:
        parse_poe_cmd("""${x-}""", config=ParseConfig())
    assert (
        excinfo.value.args[0]
        == "Bad substitution: Illegal character in parameter name '-'"
    )

    with pytest.raises(ParseError) as excinfo:
        parse_poe_cmd("""${""", config=ParseConfig())
    assert (
        excinfo.value.args[0]
        == "Unexpected end of input, expected closing '}' after '${'"
    )


def test_parse_quotes():
    tree = parse_poe_cmd(
        """
        x'y'"z"'y'x
        '' "" # this should be two empty words
        " \\"\\?*[x]${y}$ x" "$&"
        ' \\"\\?*[x]${y}$'
        '\\'''\\' ' '
        """,
        config=ParseConfig(),
    )
    print(tree.pretty())
    assert len(tree.lines) == 5
    assert tree.lines[0] == (
        (
            ("x",),
            ("y",),
            ("z",),
            ("y",),
            ("x",),
        ),
    )
    assert tree.lines[1] == ((("",),), (("",),), " this should be two empty words")
    assert tree.lines[2] == (
        ((""" "\\?*[x]""", "y", "$ x"),),
        (("$&",),),
    )
    assert tree.lines[3] == (((""" \\"\\?*[x]${y}$""",),),)
    assert tree.lines[4] == (
        (
            ("\\",),
            ("",),
            ("'",),
        ),
        ((" ",),),
    )

    first_word = tree.lines[0].words[0]
    assert first_word.segments[0].is_quoted is False
    assert first_word.segments[0].is_single_quoted is False
    assert first_word.segments[0].is_double_quoted is False
    assert first_word.segments[1].is_quoted is True
    assert first_word.segments[1].is_single_quoted is True
    assert first_word.segments[1].is_double_quoted is False
    assert first_word.segments[2].is_quoted is True
    assert first_word.segments[2].is_single_quoted is False
    assert first_word.segments[2].is_double_quoted is True


def test_parse_unmatched_quotes():
    with pytest.raises(ParseError) as excinfo:
        parse_poe_cmd(""" ok"not ok """)
    assert (
        excinfo.value.args[0] == "Unexpected end of input with unmatched double quote"
    )

    with pytest.raises(ParseError) as excinfo:
        parse_poe_cmd(r""" ok"not ok\" """)
    assert (
        excinfo.value.args[0] == "Unexpected end of input with unmatched double quote"
    )

    with pytest.raises(ParseError) as excinfo:
        parse_poe_cmd(""" ok'not ok """)
    assert (
        excinfo.value.args[0] == "Unexpected end of input with unmatched single quote"
    )


def test_invalid_features():
    with pytest.raises(ParseError) as excinfo:
        parse_poe_cmd("""end\\""")
    assert excinfo.value.args[0] == "Unexpected end of input after backslash"

    with pytest.raises(ParseError) as excinfo:
        parse_poe_cmd("""end[\\""", config=ParseConfig())
    assert (
        excinfo.value.args[0]
        == "Invalid pattern: unexpected end of input after backslash"
    )


def test_parse_globs():
    tree = parse_poe_cmd(
        """
        * ? []xyz\\ ]d [!]] [!] ]
        a*b?c[]xyz\\ ]d[!]][!] ]
        "a*b?c[]xyz\\ ]d[!]][!] ]"
        'a*b?c[]xyz\\ ]d[!]][!] ]'
        a\\*b\\?c\\[]xyz\\\\\\ ]d\\[!]]\\[!]\\ ]
        """,
        config=ParseConfig(),
    )
    print(tree.pretty())
    assert len(tree.lines) == 5
    assert tree.lines[0] == (
        (("*",),),
        (("?",),),
        (("[]xyz ]", "d"),),
        (("[!]]",),),
        (("[!]",),),
        (("]",),),
    )
    assert tree.lines[1] == (
        (("a", "*", "b", "?", "c", "[]xyz ]", "d", "[!]]", "[!]"),),
        (("]",),),
    )
    assert tree.lines[2] == ((("a*b?c[]xyz\\ ]d[!]][!] ]",),),)
    assert tree.lines[3] == ((("a*b?c[]xyz\\ ]d[!]][!] ]",),),)
    assert tree.lines[4] == ((("a*b?c[]xyz\\ ]d[!]][!] ]",),),)


def test_parse_non_globs():
    tree = Script(
        ParseCursor.from_file(
            StringIO(
                """
                ab[cd ]ef
                """
            )
        ),
        config=ParseConfig(),
    )
    print(tree.pretty())
    assert len(tree.lines) == 1
    assert tree.lines[0] == (
        (
            (
                "ab",
                "[cd",
            ),
        ),
        (("]ef",),),
    )


def test_parse_python_style_globs():
    tree = parse_poe_cmd(
        """
        * ? []xyz\\ ]d [!]] [!] ]
        a*b?c[]xyz\\ ]d[!]][!] ]
        "a*b?c[]xyz\\ ]d[!]][!] ]"
        'a*b?c[]xyz\\ ]d[!]][!] ]'
        """,
        config=ParseConfig(substitute_nodes={Glob: PythonGlob}),
    )
    print(tree.pretty())
    assert len(tree.lines) == 4
    assert tree.lines[0] == (
        (("*",),),
        (("?",),),
        (("[]xyz\\ ]", "d"),),
        (("[!]]",),),
        (("[!] ]",),),
    )
    assert tree.lines[1] == (
        (
            (
                "a",
                "*",
                "b",
                "?",
                "c",
                "[]xyz\\ ]",
                "d",
                "[!]]",
                "[!] ]",
            ),
        ),
    )
    assert tree.lines[2] == ((("a*b?c[]xyz\\ ]d[!]][!] ]",),),)
    assert tree.lines[3] == ((("a*b?c[]xyz\\ ]d[!]][!] ]",),),)


def test_parse_python_style_non_globs():
    tree = Script(
        ParseCursor.from_file(
            StringIO(
                """
                ab[c d
                """
            )
        ),
        config=ParseConfig(substitute_nodes={Glob: PythonGlob}),
    )
    print(tree.pretty())
    assert len(tree.lines) == 1
    assert tree.lines[0] == (
        (("ab", "[c"),),
        (("d",),),
    )


def test_parse_line_breaks():
    tree = Script(
        ParseCursor.from_string(
            """
            one
            two;three


            "four";;;five;

            " ;"six'; '
            """
        )
    )
    print(tree.pretty())
    lines = tree.command_lines
    assert len(lines) == 6
    assert lines[0] == ((("one",),),)
    assert lines[1] == ((("two",),),)
    assert lines[2] == ((("three",),),)
    assert lines[3] == ((("four",),),)
    assert lines[4] == ((("five",),),)
    assert lines[5].words[0].segments == (
        (" ;",),
        ("six",),
        ("; ",),
    )


def test_parse_cursor_basics():
    chars = ParseCursor.from_string("llo")
    assert chars
    chars.pushback("h", "e")
    assert chars.take() == "h"
    assert list(chars) == list("ello")
    assert not chars
    assert not chars.take()


def test_ast_node_formatting():
    tree = parse_poe_cmd(
        """
        hello $world!
        """
    )
    assert (
        tree.pretty()
        == """Script:
    Line:
        Word:
            Segment:
                UnquotedText: 'hello'
        Word:
            Segment:
                ParamExpansion: 'world'
                UnquotedText: '!'"""
    )
    assert repr(tree) == (
        "Script(Line(Word(Segment(UnquotedText('hello'))),"
        " Word(Segment(ParamExpansion('world'), UnquotedText('!')))))"
    )


def test_ast_node_inspection():
    tree = parse_poe_cmd(
        """
        hello $world!
        """
    )
    assert tree[0][0][0][0] == "hello"
    assert tree[0][1][0][0] == "world"
    assert tree[0][1][0][1] == "!"

    assert tree[0][0][0][0].content == "hello"
    assert tree[0][0][0] != 2
    assert tree[0][0][0][0] != 2
    assert len(tree.lines[0].words[0].segments[0]) == 1
    assert len(tree.lines[0].words[0].segments[0].children[0]) == 5
