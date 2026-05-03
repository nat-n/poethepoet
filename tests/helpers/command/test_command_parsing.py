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


# ---------------------------------------------------------------------------
# resolve_template tests
# ---------------------------------------------------------------------------


class TestResolveTemplate:
    """
    Tests for resolve_template() which resolves a flat template string
    against an env dict, supporting :- and :+ operators.
    Unlike resolve_command_tokens, there is no word splitting or glob handling.
    """

    @staticmethod
    def _resolve(source, env, require_braces=False):
        from poethepoet.helpers.command import resolve_template

        return resolve_template(source, env, require_braces=require_braces)

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

        from poethepoet.helpers.command.ast_core import ParseError

        with pytest.raises(ParseError, match="Unsupported operator"):
            self._resolve("${VAR:?error}", {})

    def test_spy_dict_default_operator_var_exists(self):
        """
        SpyDict with :- when the var exists: spy intercepts the lookup
        and its return value is used instead of the default.
        """
        from poethepoet.env.template import SpyDict

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
        from poethepoet.env.template import SpyDict

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
        from poethepoet.env.template import SpyDict

        def spy(obj, key, value):
            return f"__env.{key}"

        env = SpyDict({"X": "val"}, getitem_spy=spy)
        result = self._resolve("${X:+replacement}", env, require_braces=True)
        assert result == "replacement"

    def test_spy_dict_alternate_operator_var_missing(self):
        """
        SpyDict with :+ when the var is missing: the expansion is empty.
        """
        from poethepoet.env.template import SpyDict

        def spy(obj, key, value):
            return f"__env.{key}"

        env = SpyDict({"X": "val"}, getitem_spy=spy)
        result = self._resolve("${MISSING:+replacement}", env, require_braces=True)
        assert result == ""
