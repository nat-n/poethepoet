import pytest

from poethepoet.helpers.parse import parse_poe_cmd


def test_resolve_command_tokens():
    script = parse_poe_cmd("""
        abc${thing1}def *$thing2?
        """)
    line = script.command_lines[0]

    assert list(line.resolve_tokens({"thing2": ""})) == [
        ("abcdef", None),
        ("*?", "*?"),
    ]

    assert list(line.resolve_tokens({"thing1": " space ", "thing2": "s p a c e"})) == [
        ("abc", None),
        ("space", None),
        ("def", None),
        ("*s", "*s"),
        ("p", None),
        ("a", None),
        ("c", None),
        ("e?", "e?"),
    ]

    assert list(line.resolve_tokens({"thing1": " space ", "thing2": "s p a c e"})) == [
        ("abc", None),
        ("space", None),
        ("def", None),
        ("*s", "*s"),
        ("p", None),
        ("a", None),
        ("c", None),
        ("e?", "e?"),
    ]

    assert list(
        line.resolve_tokens({"thing1": "x'[!] ]'y", "thing2": "z [foo ? "})
    ) == [
        ("abcx'[!]", None),
        ("]'ydef", None),
        ("*z", "*z"),
        ("[foo", None),
        ("?", "?"),
        ("?", "?"),
    ]

    line = parse_poe_cmd("""
        "ab$thing1* and ${thing2}? '${thing1}'" '${thing1}' ""
        """).command_lines[0]

    assert list(line.resolve_tokens({"thing1": r" *\o/", "thing2": ""})) == [
        (r"ab *\o/* and ? ' *\o/'", None),
        ("${thing1}", None),
        ("", None),
    ]

    script = parse_poe_cmd("""
        # comment
        one # comment
        two # comment
        three # comment
        # comment
        """)

    assert [
        token for line in script.command_lines for token in line.resolve_tokens({})
    ] == [
        ("one", None),
        ("two", None),
        ("three", None),
    ]


@pytest.mark.parametrize(
    ("source", "expected_tokens"),
    [
        # A group pattern may include parameter expansions and quotes
        ("[${S}]", [("[val]", "[val]")]),
        ("[$S]", [("[val]", "[val]")]),
        ("a[!${S}]b", [("a[!val]b", "a[!val]b")]),
        ("[${S:+y}]", [("[y]", "[y]")]),
        ("[$RANGE]", [("[a-c]", "[a-c]")]),
        ('x["a b"]', [("x[a b]", "x[a b]")]),
        ("[${S}][x]", [("[val][x]", "[val][x]")]),
        # ... or be split over multiple parameter expansions
        ("${OPEN}${CLOSE}", [("[ab]", "[ab]")]),
        ("[$CLOSE", [("[b]", "[b]")]),
        # Glob chars are not special inside a group
        ('["*"]', [("[*]", "[*]")]),
        ("[${S:+*?[}]", [("[*?[]", "[*?[]")]),
        ("[$STAR]", [("[*]", "[*]")]),
        # Quoted chars that would be special by their position in a group are moved
        ('["!"a]', [("[!a]", "[a!]")]),
        ('["!"]', [("[!]", "!")]),
        ('["!""-"]', [("[!-]", "[-!]")]),
        ('[!"!"]', [("[!!]", "[!!]")]),
        ('[a"]"]', [("[a]]", "[]a]")]),
        ('[!"]"a]', [("[!]a]", "[!]a]")]),
        ('[a"-"c]', [("[a-c]", "[ac-]")]),
        ('["a"-c]', [("[a-c]", "[a-c]")]),
        ('[-$RANGE"]"]', [("[-a-c]]", "[]a-c-]")]),
        # Backslash escaped chars only match themselves
        (r"[a\ b]", [("[a b]", "[a b]")]),
        (r"[a\]b]", [("[a]b]", "[]ab]")]),
        (r"[\!a]", [("[!a]", "[a!]")]),
        (r"[a\-c]", [("[a-c]", "[ac-]")]),
        (r"[\*]", [("[*]", "[*]")]),
        (r"[${S}\]x]", [("[val]x]", "[]valx]")]),
        (r'[\!"a"]', [("[!a]", "[a!]")]),
        (r"[${S:+a\]}]", [("[a]]", "[]a]")]),
        # Whitespace ends the word, and so the group
        ("[a b]", [("[a", None), ("b]", None)]),
        ("[ -f foo ]", [("[", None), ("-f", None), ("foo", None), ("]", None)]),
        ("x[a b$S]", [("x[a", None), ("bval]", None)]),
        # A group that is never closed is not a pattern
        ("[${S}", [("[val", None)]),
        ('["a b"', [("[a b", None)]),
        ('[${S}"]"', [("[val]", None)]),
        ("[!]$EMPTY", [("[!]", None)]),
        ("[ -n ${S} ]", [("[", None), ("-n", None), ("val", None), ("]", None)]),
        ("[${S}*", [("[val*", "[[]val*")]),
        # Whatever is quoted or escaped only matches itself
        ('"${GLOB}"*', [("v[1]*", "v[[]1]*")]),
        ("'a[b?'*", [("a[b?*", "a[[]b[?]*")]),
        (r"\*${S}*", [("*val*", "[*]val*")]),
        (r"\[${S}]*", [("[val]*", "[[]val]*")]),
        ("${S:+*}?", [("*?", "[*]?")]),
        ("${GLOB}", [("v[1]", "v[1]")]),
        ('"[${S}]"', [("[val]", None)]),
    ],
)
def test_resolve_glob_patterns(source, expected_tokens):
    """
    Each token is yielded with its glob pattern if it has one. The token itself is
    always what bash would pass on if the pattern matched nothing.
    """
    line = parse_poe_cmd(source).command_lines[0]
    env = {
        "S": "val",
        "GLOB": "v[1]",
        "RANGE": "a-c",
        "OPEN": "[a",
        "CLOSE": "b]",
        "STAR": "*",
    }
    assert list(line.resolve_tokens(env)) == expected_tokens


def test_resolve_alternate_value_preserves_quotes():
    """
    Quoted content inside :+ and :- operators should not be word-split.
    See https://github.com/nat-n/poethepoet/issues/333

    Each case is verified against bash behavior. Cases already covered by
    integration tests in test_cmd_param_expansion.py are not repeated here.
    """
    # Default value not applied when var is set
    line = parse_poe_cmd("echo ${FLAG:- -m 'not build'}").command_lines[0]
    assert list(line.resolve_tokens({"FLAG": "yes"})) == [
        ("echo", None),
        ("yes", None),
    ]

    # Expansion embedded in a word — leading/trailing text joins adjacent tokens
    # bash: printf '[%s]\n' x${F:+ -m 'not build'}y → [x] [-m] [not buildy]
    line = parse_poe_cmd("x${FLAG:+ -m 'not build'}y").command_lines[0]
    assert list(line.resolve_tokens({"FLAG": "yes"})) == [
        ("x", None),
        ("-m", None),
        ("not buildy", None),
    ]

    # Nested expansion in alternate value — inner value is word-split
    # bash: F=y O="hello world"; printf '[%s]\n' ${F:+ $O} → [hello] [world]
    line = parse_poe_cmd("${FLAG:+ $OTHER}").command_lines[0]
    assert list(line.resolve_tokens({"FLAG": "y", "OTHER": "hello world"})) == [
        ("hello", None),
        ("world", None),
    ]

    # Outer double quotes suppress word splitting of nested expansion
    # bash: F=y O="hello world"; printf '[%s]\n' "${F:+ $O}" → [ hello world]
    line = parse_poe_cmd('"${FLAG:+ $OTHER}"').command_lines[0]
    assert list(line.resolve_tokens({"FLAG": "y", "OTHER": "hello world"})) == [
        (" hello world", None),
    ]

    # Nested operations: alternate value containing default value with quotes
    # bash: F=y; printf '[%s]\n' ${F:+${UNSET:-'hello world'}} → [hello world]
    line = parse_poe_cmd("${FLAG:+${UNSET:-'hello world'}}").command_lines[0]
    assert list(line.resolve_tokens({"FLAG": "y"})) == [
        ("hello world", None),
    ]

    # Empty alternate value produces nothing
    # bash: F=y; printf '[%s]\n' A${F:+}B → [AB]
    line = parse_poe_cmd("A${FLAG:+}B").command_lines[0]
    assert list(line.resolve_tokens({"FLAG": "y"})) == [
        ("AB", None),
    ]


# ---------------------------------------------------------------------------
# Template.resolve tests
# ---------------------------------------------------------------------------


class TestResolveTemplate:
    """
    Tests for Template.resolve() which resolves a flat template string
    against an env dict, supporting :- and :+ operators.
    Unlike Line.resolve_tokens, there is no word splitting or glob handling.
    """

    @staticmethod
    def _resolve(source, env, require_braces=False):
        from poethepoet.helpers.parse import parse_template

        return parse_template(source, require_braces=require_braces).resolve(env)

    def test_plain_text(self):
        assert self._resolve("hello world", {}) == "hello world"

    def test_empty_string(self):
        assert self._resolve("", {}) == ""

    def test_simple_var(self):
        assert self._resolve("hello $NAME", {"NAME": "alice"}) == "hello alice"

    def test_braced_var(self):
        assert self._resolve("hello ${NAME}", {"NAME": "alice"}) == "hello alice"

    def test_missing_var(self):
        """
        Missing var resolves to empty string.
        """
        assert self._resolve("hello ${NAME}", {}) == "hello "

    def test_default_value_unset(self):
        assert self._resolve("${NAME:-world}", {}) == "world"

    def test_default_value_empty(self):
        assert self._resolve("${NAME:-world}", {"NAME": ""}) == "world"

    def test_default_value_set(self):
        assert self._resolve("${NAME:-world}", {"NAME": "alice"}) == "alice"

    def test_alternate_value_set(self):
        assert self._resolve("${DEBUG:+--verbose}", {"DEBUG": "1"}) == "--verbose"

    def test_alternate_value_unset(self):
        assert self._resolve("${DEBUG:+--verbose}", {}) == ""

    def test_alternate_value_empty(self):
        assert self._resolve("${DEBUG:+--verbose}", {"DEBUG": ""}) == ""

    def test_nested_default(self):
        assert self._resolve("${A:-${B:-fallback}}", {}) == "fallback"

    def test_nested_default_inner_set(self):
        assert self._resolve("${A:-${B:-fallback}}", {"B": "found"}) == "found"

    def test_nested_default_outer_set(self):
        assert self._resolve("${A:-${B:-fallback}}", {"A": "outer"}) == "outer"

    def test_nested_alternate_in_default(self):
        """
        ${A:-${B:+yes}} — A unset, B set → "yes"
        """
        assert self._resolve("${A:-${B:+yes}}", {"B": "1"}) == "yes"

    def test_composition(self):
        """
        Multiple expansions composed in a single template.
        """
        result = self._resolve(
            "${SCHEME:-https}://${HOST:-localhost}:${PORT:-8080}",
            {"HOST": "example.com"},
        )
        assert result == "https://example.com:8080"

    def test_require_braces(self):
        """
        With require_braces=True, bare $VAR is literal text.
        """
        result = self._resolve(
            "$NAME and ${NAME}", {"NAME": "alice"}, require_braces=True
        )
        assert result == "$NAME and alice"

    def test_escape_dollar(self):
        r"""
        \$ is a literal dollar, not an expansion.
        """
        assert self._resolve(r"\${NAME}", {"NAME": "alice"}) == "${NAME}"

    def test_escape_backslash(self):
        r"""
        \\ is a literal backslash.
        """
        assert self._resolve(r"path\\to", {}) == "path\\to"

    def test_backslash_before_regular_char(self):
        r"""
        \n passes through literally (not bash-style escaping).
        """
        assert self._resolve(r"hello\nworld", {}) == "hello\\nworld"

    def test_literal_dollar_non_var(self):
        """
        $ before a non-var character is literal.
        """
        assert self._resolve("cost is $5", {}) == "cost is $5"

    def test_trailing_dollar(self):
        assert self._resolve("price is $", {}) == "price is $"

    def test_empty_alternate_argument(self):
        """
        ${VAR:+} with an empty alternate argument produces empty string
        even when the var is set.
        """
        assert self._resolve("A${FOO:+}B", {"FOO": "set"}) == "AB"

    def test_whitespace_in_value_preserved(self):
        """
        Whitespace in variable values is preserved literally — no word
        splitting occurs in template resolution.
        """
        assert self._resolve("${FOO}", {"FOO": " x "}) == " x "

    def test_whitespace_in_default_preserved(self):
        """
        Whitespace in :- default argument is preserved literally.
        """
        assert self._resolve("${FOO:-a b c}", {}) == "a b c"

    def test_surrounding_text_preserved(self):
        """
        Text surrounding an expansion is preserved in the output.
        """
        assert self._resolve("A${FOO}B", {"FOO": "x"}) == "AxB"
        assert self._resolve("A${FOO}B", {}) == "AB"
        assert self._resolve("A${FOO:-bar}B", {}) == "AbarB"
        assert self._resolve("A${FOO:+bar}B", {"FOO": "x"}) == "AbarB"

    def test_require_braces_applies_inside_operator_arguments(self):
        """
        require_braces is inherited by the entire parse tree, so bare $VAR
        inside a :- argument is also treated as literal. Use ${VAR} to get
        expansion inside operator arguments when require_braces is set.
        """
        # Bare $B is literal when require_braces=True
        result = self._resolve("${A:-$B}", {"B": "inner"}, require_braces=True)
        assert result == "$B"

        # Braced ${B} still expands
        result = self._resolve("${A:-${B}}", {"B": "inner"}, require_braces=True)
        assert result == "inner"

    def test_invalid_operator_raises_parse_error(self):
        """
        Unsupported operators like :? produce a ParseError that propagates
        to the caller.
        """
        import pytest

        from poethepoet.helpers.parse.core import ParseError

        with pytest.raises(ParseError, match="Unsupported operator"):
            self._resolve("${VAR:?error}", {})

    def test_spy_dict_default_operator_var_exists(self):
        """
        SpyDict with :- when the var exists: spy intercepts the lookup
        and its return value is used instead of the default.
        """
        from poethepoet.env.utils import SpyDict

        accessed: dict[str, str] = {}

        def spy(obj, key, value):
            accessed[key] = value
            return f"__env.{key}"

        env = SpyDict({"X": "val"}, getitem_spy=spy)
        result = self._resolve("${X:-fallback}", env, require_braces=True)
        assert result == "__env.X"
        assert accessed == {"X": "val"}

    def test_spy_dict_default_operator_var_missing(self):
        """
        SpyDict with :- when the var is missing: spy is not called,
        and the default value is used directly.
        """
        from poethepoet.env.utils import SpyDict

        accessed: dict[str, str] = {}

        def spy(obj, key, value):
            accessed[key] = value
            return f"__env.{key}"

        env = SpyDict({"X": "val"}, getitem_spy=spy)
        result = self._resolve("${MISSING:-fallback}", env, require_braces=True)
        assert result == "fallback"
        assert "MISSING" not in accessed

    def test_spy_dict_alternate_operator_var_exists(self):
        """
        SpyDict with :+ when the var exists: spy returns a truthy value,
        so the alternate is used (not the spy's return value).
        """
        from poethepoet.env.utils import SpyDict

        def spy(obj, key, value):
            return f"__env.{key}"

        env = SpyDict({"X": "val"}, getitem_spy=spy)
        result = self._resolve("${X:+replacement}", env, require_braces=True)
        assert result == "replacement"

    def test_spy_dict_alternate_operator_var_missing(self):
        """
        SpyDict with :+ when the var is missing: the expansion is empty.
        """
        from poethepoet.env.utils import SpyDict

        def spy(obj, key, value):
            return f"__env.{key}"

        env = SpyDict({"X": "val"}, getitem_spy=spy)
        result = self._resolve("${MISSING:+replacement}", env, require_braces=True)
        assert result == ""


class TestParseTemplateAndResolve:
    """
    Tests for parse_template() and Template.resolve() as composable steps:
    parse once, resolve many times.
    """

    def test_parse_template_returns_template_node(self):
        from poethepoet.helpers.parse import parse_template
        from poethepoet.helpers.parse.template import Template

        tree = parse_template("hello $NAME")
        assert isinstance(tree, Template)

    def test_template_resolve_returns_resolved_string(self):
        from poethepoet.helpers.parse import parse_template

        tree = parse_template("hello $NAME")
        assert tree.resolve({"NAME": "alice"}) == "hello alice"

    def test_parse_once_resolve_multiple_times(self):
        """A parsed Template can be resolved repeatedly with different envs."""
        from poethepoet.helpers.parse import parse_template

        source = "${SCHEME:-https}://${HOST:-localhost}:${PORT:-8080}"
        tree = parse_template(source)
        assert tree.resolve({"HOST": "example.com"}) == "https://example.com:8080"
        assert (
            tree.resolve({"HOST": "other.com", "PORT": "9000"})
            == "https://other.com:9000"
        )

    def test_parse_template_require_braces_flows_through(self):
        from poethepoet.helpers.parse import parse_template

        tree = parse_template("$BARE ${BRACED}", require_braces=True)
        result = tree.resolve({"BARE": "x", "BRACED": "y"})
        assert result == "$BARE y"
