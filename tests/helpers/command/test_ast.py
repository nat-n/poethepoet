from poethepoet.helpers.command import parse_poe_cmd
from poethepoet.helpers.command.ast import (
    Line,
    ParamExpansion,
    ParseConfig,
    Segment,
    Word,
)


def test_parse_comments():
    tree = parse_poe_cmd(
        """# 1
            2 3  # 4 ; 5

            # 6 # 7""",
        config=ParseConfig(),
    )
    print(tree.pretty())
    assert len(tree.lines) == 3
    assert tree.lines[0].comment == " 1"
    assert tree.lines[1] == ((("2",),), (("3",),), " 4 ; 5")
    assert tree.lines[2].comment == " 6 # 7"


def test_parse_params():
    tree = parse_poe_cmd(
        """
        $x${y}$ z
        $x ${y} $ z
        a$x? a${y}b a$? z
        "$x${y}$ z"
        "$x ${y} $ z"
        "a$x? a${y}b a$? z"
        '$x${y}$ z'
        '$x ${y} $ z'
        'a$x? a${y}b a$? z'
        """,
        config=ParseConfig(),
    )
    print(tree.pretty())
    assert len(tree.lines) == 9
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
    assert tree.lines[5] == ((("a", "x", "? a", "y", "b a", "$? z"),),)
    assert tree.lines[6] == ((("$x${y}$ z",),),)
    assert tree.lines[7] == ((("$x ${y} $ z",),),)
    assert tree.lines[8] == ((("a$x? a${y}b a$? z",),),)


def test_parse_quotes():
    tree = parse_poe_cmd(
        """
        x'y'"z"'y'x
        '' "" # this should be two empty words
        " \\"\\?*[x]${y}$"
        ' \\"\\?*[x]${y}$'
        '\\'''\\'
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
    assert tree.lines[1] == ((tuple(),), (tuple(),), " this should be two empty words")
    assert tree.lines[2] == (((""" "\\?*[x]""", "y", "$"),),)
    assert tree.lines[3] == (((""" \\"\\?*[x]${y}$""",),),)
    assert tree.lines[4] == (
        (
            ("\\",),
            tuple(),
            ("'",),
        ),
    )


def test_parse_globs():
    tree = parse_poe_cmd(
        """
        * ? []xyz\ ]
        a*b?c[]xyz\ ]d
        "a*b?c[]xyz\ ]d"
        'a*b?c[]xyz\ ]d'
        """,
        config=ParseConfig(),
    )
    print(tree.pretty())
    assert len(tree.lines) == 4
    assert tree.lines[0] == (
        (("*",),),
        (("?",),),
        (("[]xyz ]",),),
    )
    assert tree.lines[1] == ((("a", "*", "b", "?", "c", "[]xyz ]", "d"),),)
    assert tree.lines[2] == ((("a*b?c[]xyz\ ]d",),),)
    assert tree.lines[3] == ((("a*b?c[]xyz\ ]d",),),)
