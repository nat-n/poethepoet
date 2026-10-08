import shlex
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("expression", "output", "env"),
    [
        # basic parameter value expansion
        (r"$", "$", {}),
        (r"A${FOO}B", "AB", {}),
        (r"A${FOO}B", "AB", {"FOO": ""}),
        (r"A${FOO}B", "A x B", {"FOO": " x "}),
        (r"A${FOO}B", "A B", {"FOO": "   "}),
        (r"A${FOO}B", "AfooB", {"FOO": "foo"}),
        # default value operator
        (r"A${FOO:-}B", "AB", {}),
        (r"A${FOO:-bar}B", "AbarB", {}),
        (r"A${FOO:-bar}B", "AbarB", {"FOO": ""}),
        (r"A${FOO:-bar}B", "AfooB", {"FOO": "foo"}),
        # alternate value operator
        (r"A${FOO:+bar}B", "AB", {}),
        (r"A${FOO:+bar}B", "AB", {"FOO": ""}),
        (r"A${FOO:+}B", "AB", {"FOO": "foo"}),
        (r"A${FOO:+bar}B", "AbarB", {"FOO": "foo"}),
        # recursion
        (r"A${FOO:->${BAR:+ ${BAZ:- the end }<}}B", "A> the end <B", {"BAR": "X"}),
        # weird argument content
        (r"A${FOO:- !&%;#($)@}B", "A !&%;#($)@B", {}),
        (r'"A${FOO:-?.*[x]}B"', "A?.*[x]B", {}),
        (
            r"""A${FOO:-

            hey

            }B""",
            "A hey B",
            {},
        ),
    ],
)
def test_param_expansion_operations(
    expression, output, env, run_poe, temp_pyproject, tmp_path
):
    stdout_path = tmp_path / "output.txt"
    stdout_path.touch(exist_ok=True)
    project_toml = f'''
    [tool.poe.tasks.echo-expression]
    cmd = """echo {expression}"""
    capture_stdout = "{stdout_path.as_posix()}"
    '''
    project_path = temp_pyproject(project_toml)
    result = run_poe("echo-expression", cwd=project_path, env=env)

    print(project_toml)
    print("result", result)

    assert result.code == 0

    with stdout_path.open() as stdout_file:
        assert stdout_file.read() == f"{output}\n", (
            "Task output should match test parameter"
        )


@pytest.mark.parametrize(
    ("cmd_content", "env", "expected_tokens"),
    [
        #
        # ---- Core regression cases for issue #333 ----
        #
        # Single-quoted whitespace inside ${VAR:+...} must remain a single token.
        # Validated in bash 5.2: <pytest><-m><not build>
        pytest.param(
            "echo pytest ${SKIP_BUILD:+ -m 'not build'}",
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "-m", "not build"],
            id="alt_value_single_quoted_ws",
        ),
        # Double-quoted whitespace inside ${VAR:+...} must remain a single token.
        # Validated in bash 5.2: <pytest><-m><not build>
        pytest.param(
            'echo pytest ${SKIP_BUILD:+ -m "not build"}',
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "-m", "not build"],
            id="alt_value_double_quoted_ws",
        ),
        # The same applies to the default-value operator ${VAR:-...}.
        # Validated in bash 5.2: <pytest><-m><not build>
        pytest.param(
            "echo pytest ${MARKER:- -m 'not build'}",
            {},
            ["echo", "pytest", "-m", "not build"],
            id="default_value_single_quoted_ws",
        ),
        # Quoted segment concatenated with adjacent unquoted text must form a
        # single concatenated token (no word break inside the quoted region).
        # Validated in bash 5.2: <pytest><--marker=not build>
        pytest.param(
            "echo pytest ${SKIP_BUILD:+--marker='not build'}",
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "--marker=not build"],
            id="alt_value_quoted_concat_unquoted",
        ),
        # Mixed quoted/unquoted siblings: word splitting happens between them
        # but never inside the quoted region.
        # Validated in bash 5.2: <pytest><-m><not build><--rest>
        pytest.param(
            "echo pytest ${SKIP_BUILD:+ -m 'not build' --rest}",
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "-m", "not build", "--rest"],
            id="alt_value_mixed_quoted_unquoted_siblings",
        ),
        # Multiple separate quoted-with-whitespace words inside one expansion.
        # Validated in bash 5.2: <pytest><word1><word two><word3>
        pytest.param(
            "echo pytest ${SKIP_BUILD:+ word1 'word two' word3}",
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "word1", "word two", "word3"],
            id="alt_value_multiple_quoted_words",
        ),
        # Two adjacent single-quoted segments concatenate without a word break.
        # Validated in bash 5.2: <pytest><a bc d>
        pytest.param(
            "echo pytest ${SKIP_BUILD:+'a b''c d'}",
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "a bc d"],
            id="alt_value_concat_two_quoted",
        ),
        #
        # ---- Possibly related issues ----
        #
        # Backslash-escaped space inside an unquoted operator argument should
        # bind the two halves into a single token, just like in bash.
        # Validated in bash 5.2: <pytest><-m><not build>
        pytest.param(
            r"echo pytest ${SKIP_BUILD:+ -m not\ build}",
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "-m", "not build"],
            id="alt_value_backslash_escaped_space",
        ),
        # Nested expansion in a double-quoted region inside the operator argument:
        # the inner expansion is performed and the result remains a single token
        # (because the inner is double-quoted).
        # Validated in bash 5.2: <pytest><-m><not build>
        pytest.param(
            'echo pytest ${SKIP_BUILD:+ -m "${MARKER:-not build}"}',
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "-m", "not build"],
            id="alt_value_nested_double_quoted",
        ),
        # Nested operator expansion in an unquoted context: the inner
        # ${B:+...} must also preserve its quoted regions, not just the
        # outermost level. This validates that the fix composes recursively.
        # Validated in bash 5.2: <echo><pytest><-m><not build>
        pytest.param(
            "echo pytest ${A:+ ${B:+ -m 'not build'}}",
            {"A": "1", "B": "1"},
            ["echo", "pytest", "-m", "not build"],
            id="alt_value_nested_unquoted_operator",
        ),
        # Nested expansion in a single-quoted region inside the operator argument:
        # the inner ${...} is NOT expanded, it is taken literally.
        # Validated in bash 5.2: <pytest><-m><${MARKER:-not build}>
        pytest.param(
            "echo pytest ${SKIP_BUILD:+ -m '${MARKER:-not build}'}",
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "-m", "${MARKER:-not build}"],
            id="alt_value_nested_single_quoted_literal",
        ),
        # A bare $VAR inside a single-quoted operator argument is literal.
        # Validated in bash 5.2: <pytest><-m><$MARKER is empty>
        pytest.param(
            "echo pytest ${SKIP_BUILD:+ -m '$MARKER is empty'}",
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "-m", "$MARKER is empty"],
            id="alt_value_dollar_in_single_quotes_literal",
        ),
        # Glob characters inside a quoted operator argument must not be expanded
        # nor cause the token to be treated as a glob pattern.
        # Validated in bash 5.2: <pytest><*.py>
        pytest.param(
            "echo pytest ${SKIP_BUILD:+ '*.py'}",
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "*.py"],
            id="alt_value_quoted_glob_literal",
        ),
        # A tab inside a quoted operator argument is preserved verbatim, not
        # collapsed to a space and not used as a word break.
        # Validated in bash 5.2: <pytest><-m><a\tb>
        pytest.param(
            "echo pytest ${SKIP_BUILD:+ -m 'a\tb'}",
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "-m", "a\tb"],
            id="alt_value_quoted_tab_preserved",
        ),
        # Quoted whitespace-only argument should produce a token containing
        # exactly that whitespace, not a single collapsed space.
        # Validated in bash 5.2: <pytest><  >
        pytest.param(
            "echo pytest ${SKIP_BUILD:+ '  '}",
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "  "],
            id="alt_value_quoted_whitespace_only",
        ),
        #
        # ---- Existing behavior captured as regression tests ----
        #
        # Outer-quoted expansion: the entire expansion is a single token.
        # Validated in bash 5.2: <pytest><a b c>
        pytest.param(
            'echo pytest "${SKIP_BUILD:+a b c}"',
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "a b c"],
            id="outer_quoted_expansion_single_token",
        ),
        # Unquoted whitespace inside an unquoted expansion is subject to word
        # splitting, exactly as in bash.
        # Validated in bash 5.2: <pytest><-m><not><build>
        pytest.param(
            "echo pytest ${SKIP_BUILD:+ -m not build}",
            {"SKIP_BUILD": "1"},
            ["echo", "pytest", "-m", "not", "build"],
            id="alt_value_unquoted_word_split",
        ),
        # Empty :+ expansion (variable unset) drops the whole substitution.
        # Validated in bash 5.2: <pytest>
        pytest.param(
            "echo pytest ${SKIP_BUILD:+ -m 'not build'}",
            {},
            ["echo", "pytest"],
            id="alt_value_unset_drops_substitution",
        ),
    ],
)
def test_param_expansion_argument_tokenization(
    cmd_content, env, expected_tokens, run_poe, temp_pyproject
):
    """
    Verify that the tokenization of cmd tasks containing parameter expansion
    operators (`${VAR:+...}` / `${VAR:-...}`) matches bash semantics, in
    particular that quoted regions inside the operator argument suppress word
    splitting and that quote characters themselves are stripped from the
    resulting tokens.

    Each expected_tokens value in this parametrization has been validated
    against GNU bash 5.2 using `printf '<%s>' "$@"` to make token boundaries
    visible.
    """
    project_toml = f"""
    [tool.poe.tasks.run]
    cmd = '''{cmd_content}'''
    """
    project_path = temp_pyproject(project_toml)
    result = run_poe("run", cwd=project_path, env=env)

    assert result.code == 0, (
        f"poe exited with {result.code}\n"
        f"capture: {result.capture!r}\n"
        f"stderr:  {result.stderr!r}"
    )
    expected_capture = f"Poe => {shlex.join(expected_tokens)}\n"
    assert result.capture == expected_capture, (
        "cmd task tokenization should match bash semantics\n"
        f"  cmd:      {cmd_content!r}\n"
        f"  env:      {env!r}\n"
        f"  expected: {expected_capture!r}\n"
        f"  actual:   {result.capture!r}"
    )


BRACKET_GLOB_BUG = pytest.mark.xfail(
    strict=True, reason="bracket glob swallows parameter expansion and quotes"
)
UNMATCHED_GLOB_BUG = pytest.mark.xfail(
    strict=True, reason="unmatched glob passes the escaped pattern, not the word"
)


@pytest.mark.parametrize(
    ("cmd_args", "expected_args"),
    [
        pytest.param("[${S}]", ["[val]"], marks=BRACKET_GLOB_BUG, id="brace"),
        pytest.param("[$S]", ["[val]"], marks=BRACKET_GLOB_BUG, id="bare"),
        pytest.param("x[${S}]", ["x[val]"], marks=BRACKET_GLOB_BUG, id="prefix"),
        pytest.param(
            "a[${S}]b c", ["a[val]b", "c"], marks=BRACKET_GLOB_BUG, id="infix"
        ),
        pytest.param("[!${S}]", ["[!val]"], marks=BRACKET_GLOB_BUG, id="negated"),
        pytest.param(
            "[${S:+y}]", ["[y]"], marks=BRACKET_GLOB_BUG, id="alt_value_operator"
        ),
        pytest.param('x["a b"]', ["x[a b]"], marks=BRACKET_GLOB_BUG, id="quoted"),
        pytest.param(
            '"${G}"*', ["v[1]*"], marks=UNMATCHED_GLOB_BUG, id="quoted_glob_value"
        ),
        pytest.param("'a[b'*", ["a[b*"], marks=UNMATCHED_GLOB_BUG, id="quoted_bracket"),
        pytest.param(
            "'a?b'*", ["a?b*"], marks=UNMATCHED_GLOB_BUG, id="quoted_question_mark"
        ),
        pytest.param(
            r"\*${S}*", ["*val*"], marks=UNMATCHED_GLOB_BUG, id="escaped_star"
        ),
        pytest.param("${S}*", ["val*"], id="param_then_star"),
        pytest.param("[abc]", ["[abc]"], id="literal_bracket_glob"),
        pytest.param('"[${S}]"', ["[val]"], id="double_quoted"),
        pytest.param(r"\[${S}]", ["[val]"], id="escaped_bracket"),
        pytest.param("'[${S}]'", ["[${S}]"], id="single_quoted"),
        pytest.param("${S}[x]", ["val[x]"], id="param_then_bracket_glob"),
        pytest.param("${G}", ["v[1]"], id="param_with_glob_chars"),
    ],
)
def test_param_expansion_in_unmatched_glob(
    cmd_args, expected_args, run_poe, temp_pyproject
):
    """
    A glob word that matches nothing is passed on as bash would: the word after
    parameter expansion and quote removal.
    """
    project_path = temp_pyproject(
        f"""
        [tool.poe.tasks.run]
        cmd = '''echo {cmd_args}'''
        """
    )
    result = run_poe("run", cwd=project_path, env={"S": "val", "G": "v[1]"})

    assert result.code == 0, result.capture
    assert result.capture == f"Poe => {shlex.join(['echo', *expected_args])}\n"


@pytest.mark.parametrize(
    ("cmd_args", "expected_matches"),
    [
        pytest.param("[${S}]", ["a", "v"], marks=BRACKET_GLOB_BUG, id="brace"),
        pytest.param("[$S]", ["a", "v"], marks=BRACKET_GLOB_BUG, id="bare"),
        pytest.param("x[${S}]", ["xa"], marks=BRACKET_GLOB_BUG, id="prefix"),
        pytest.param("${S}*", ["valX"], id="param_then_star"),
        pytest.param("[abc]", ["a"], id="literal_bracket_glob"),
        pytest.param(r"\[${S}]", ["[val]"], id="escaped_bracket"),
        pytest.param("'[${S}]'", ["[${S}]"], id="single_quoted"),
    ],
)
def test_param_expansion_in_matched_glob(
    cmd_args, expected_matches, run_poe, temp_pyproject, tmp_path
):
    """
    A glob word is matched against files after parameter expansion, so the
    pattern a bracket expression contributes is the expanded value. Matches are
    compared by file name, ignoring order.
    """
    for name in ("v", "a", "S", "$", "{", "}", "valX", "x", "xa"):
        (tmp_path / name).touch()
    project_path = temp_pyproject(
        f"""
        [tool.poe.tasks.run]
        cmd = '''echo {cmd_args}'''
        """
    )
    result = run_poe("run", cwd=project_path, env={"S": "val"})

    assert result.code == 0, result.capture
    assert result.capture.startswith("Poe => echo ")
    args = shlex.split(result.capture)[3:]
    assert sorted(Path(arg).name for arg in args) == expected_matches
