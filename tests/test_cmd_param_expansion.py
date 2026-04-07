import shlex

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
        assert (
            stdout_file.read() == f"{output}\n"
        ), "Task output should match test parameter"


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
