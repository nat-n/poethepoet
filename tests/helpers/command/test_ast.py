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
            (":-", ()),
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


# ---------------------------------------------------------------------------
# Template AST node tests
# ---------------------------------------------------------------------------


class TestTemplateParsing:
    """
    Tests for the Template and TemplateText AST nodes.
    Template is a flat parser (no line/word/segment hierarchy) for template
    strings that supports parameter expansion with :- and :+ operators.
    """

    @staticmethod
    def _parse(source, require_braces=False):
        from poethepoet.helpers.command.ast import Template

        config = ParseConfig(require_braces=require_braces)
        return Template(ParseCursor.from_string(source), config)

    def test_plain_text(self):
        """
        Template with no parameter expansion is a single TemplateText child.
        """
        tree = self._parse("hello world")
        assert len(tree) == 1
        assert tree[0] == "hello world"

    def test_empty_string(self):
        """
        Empty string produces an empty Template.
        """
        tree = self._parse("")
        assert len(tree) == 0

    def test_simple_braced_var(self):
        """
        ${VAR} is parsed as a ParamExpansion.
        """
        tree = self._parse("hello ${NAME} end")
        assert len(tree) == 3
        assert tree[0] == "hello "
        assert tree[1].param_name == "NAME"
        assert tree[1].operation is None
        assert tree[2] == " end"

    def test_bare_var(self):
        """
        $VAR (without braces) is parsed as a ParamExpansion.
        """
        tree = self._parse("hello $NAME end")
        assert len(tree) == 3
        assert tree[0] == "hello "
        assert tree[1].param_name == "NAME"
        assert tree[2] == " end"

    def test_require_braces_rejects_bare_var(self):
        """
        With require_braces=True, bare $VAR is treated as literal text.
        The $ creates a node boundary but the content is correct.
        """
        tree = self._parse("hello $NAME end", require_braces=True)
        from poethepoet.helpers.command.ast import ParamExpansion

        assert all(not isinstance(child, ParamExpansion) for child in tree)
        assert "".join(child.content for child in tree) == "hello $NAME end"

    def test_require_braces_accepts_braced_var(self):
        """
        With require_braces=True, ${VAR} still works.
        """
        tree = self._parse("hello ${NAME} end", require_braces=True)
        assert len(tree) == 3
        assert tree[0] == "hello "
        assert tree[1].param_name == "NAME"
        assert tree[2] == " end"

    def test_default_operator(self):
        """
        ${VAR:-default} is parsed with a ParamOperation.
        """
        tree = self._parse("${NAME:-world}")
        assert len(tree) == 1
        assert tree[0].param_name == "NAME"
        assert tree[0].operation is not None
        assert tree[0].operation.operator == ":-"

    def test_alternate_operator(self):
        """
        ${VAR:+alternate} is parsed with a ParamOperation.
        """
        tree = self._parse("${DEBUG:+--verbose}")
        assert len(tree) == 1
        assert tree[0].param_name == "DEBUG"
        assert tree[0].operation is not None
        assert tree[0].operation.operator == ":+"

    def test_nested_operators(self):
        """
        Nested operators: ${A:-${B:-fallback}}.
        """
        tree = self._parse("${A:-${B:-fallback}}")
        assert len(tree) == 1
        assert tree[0].param_name == "A"
        assert tree[0].operation.operator == ":-"
        # The argument contains a nested ParamExpansion
        inner_segments = tree[0].operation.argument.segments
        assert len(inner_segments) == 1
        # The inner segment has a ParamExpansion child
        inner_param = inner_segments[0][0]
        assert inner_param.param_name == "B"
        assert inner_param.operation.operator == ":-"

    def test_dollar_at_end(self):
        """
        A trailing $ is treated as literal text.
        The $ creates a node boundary but all content is TemplateText.
        """
        tree = self._parse("price is $")
        from poethepoet.helpers.command.ast import ParamExpansion

        assert all(not isinstance(child, ParamExpansion) for child in tree)
        assert "".join(child.content for child in tree) == "price is $"

    def test_dollar_before_non_var_char(self):
        """
        $ followed by a non-variable character is literal.
        """
        tree = self._parse("cost is $5")
        from poethepoet.helpers.command.ast import ParamExpansion

        assert all(not isinstance(child, ParamExpansion) for child in tree)
        assert "".join(child.content for child in tree) == "cost is $5"

    def test_escape_dollar(self):
        r"""
        \$ is an escaped dollar sign, not a param expansion.
        """
        tree = self._parse(r"price is \$5")
        assert len(tree) == 1
        assert tree[0] == "price is $5"

    def test_escape_backslash(self):
        r"""
        \\ is an escaped backslash.
        """
        tree = self._parse(r"path\\to")
        assert len(tree) == 1
        assert tree[0] == "path\\to"

    def test_backslash_before_regular_char(self):
        r"""
        \x (where x is not $ or \) passes through literally as \x.
        This matches the current regex template behavior.
        """
        tree = self._parse(r"hello\nworld")
        assert len(tree) == 1
        assert tree[0] == "hello\\nworld"

    def test_no_quote_handling(self):
        """
        Single and double quotes are treated as literal characters.
        Template does NOT parse quoting.
        """
        tree = self._parse('it\'s a "test"')
        assert len(tree) == 1
        assert tree[0] == 'it\'s a "test"'

    def test_no_word_splitting(self):
        """
        Whitespace is preserved literally in Template, no word splitting.
        """
        tree = self._parse("hello   world\ttab")
        assert len(tree) == 1
        assert tree[0] == "hello   world\ttab"

    def test_no_glob_handling(self):
        """
        Glob characters *, ?, [ are treated as literal.
        """
        tree = self._parse("files: *.py [a-z] foo?")
        assert len(tree) == 1
        assert tree[0] == "files: *.py [a-z] foo?"

    def test_no_comment_handling(self):
        """
        # is treated as literal text, not a comment.
        """
        tree = self._parse("count # items")
        assert len(tree) == 1
        assert tree[0] == "count # items"

    def test_no_semicolon_handling(self):
        """
        ; is treated as literal text, not a line separator.
        """
        tree = self._parse("a;b;c")
        assert len(tree) == 1
        assert tree[0] == "a;b;c"

    def test_multiple_expansions(self):
        """
        Multiple param expansions in a single template.
        """
        tree = self._parse("${A}/${B}/${C}")
        assert len(tree) == 5
        assert tree[0].param_name == "A"
        assert tree[1] == "/"
        assert tree[2].param_name == "B"
        assert tree[3] == "/"
        assert tree[4].param_name == "C"

    def test_adjacent_expansions(self):
        """
        Param expansions with no text between them.
        """
        tree = self._parse("${A}${B}")
        assert len(tree) == 2
        assert tree[0].param_name == "A"
        assert tree[1].param_name == "B"

    def test_operator_argument_preserves_special_chars(self):
        """
        Operator arguments can contain characters that would be special in
        command parsing (semicolons, hashes, globs) but are treated literally
        inside ${...:-...}. Quotes ARE still special (bash semantics).
        """
        tree = self._parse("${X:-#1; *.py}")
        assert len(tree) == 1
        assert tree[0].param_name == "X"
        assert tree[0].operation.operator == ":-"
        # Verify the argument captured the full content including special chars
        argument_segments = tree[0].operation.argument.segments
        assert len(argument_segments) == 1
        argument_text = "".join(element.content for element in argument_segments[0])
        assert argument_text == "#1; *.py"

    def test_escaped_dollar_before_braced_var(self):
        r"""
        \${VAR} should produce literal ${VAR}, not an expansion.
        """
        tree = self._parse(r"\${NAME}")
        assert len(tree) == 1
        assert tree[0] == "${NAME}"

    def test_mixed_escaped_and_real_expansions(self):
        r"""
        Mix of escaped and real expansions.
        """
        tree = self._parse(r"\${SKIP} but ${KEEP}")
        from poethepoet.helpers.command.ast import ParamExpansion

        # The escaped ${SKIP} is text, ${KEEP} is a real expansion
        text_content = "".join(
            child.content for child in tree if not isinstance(child, ParamExpansion)
        )
        param_names = [
            child.param_name for child in tree if isinstance(child, ParamExpansion)
        ]
        assert text_content == "${SKIP} but "
        assert param_names == ["KEEP"]

    def test_double_backslash_before_dollar(self):
        r"""
        \\$FOO — the \\ is consumed as an escaped backslash producing a
        single \, then $FOO is parsed as a param expansion.
        """
        tree = self._parse(r"\\$FOO")
        # Two children: TemplateText("\") followed by ParamExpansion("FOO")
        assert len(tree) == 2
        assert tree[0] == "\\"
        assert tree[1].param_name == "FOO"
