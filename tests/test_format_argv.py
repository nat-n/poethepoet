"""
Unit tests for ``PoeTaskArgs.format_argv`` — the inverse of ``parse``, used
when a module-style script task needs to forward declared args (with defaults
applied) into a ``python -m`` subprocess.
"""

import pytest

from poethepoet.io import PoeIO
from poethepoet.task.args import PoeTaskArgs


def _args(args_def):
    return PoeTaskArgs(args_def, "task", PoeIO(make_default=False))


def test_positional_emits_value():
    args = _args([{"name": "x", "positional": True}])
    assert args.format_argv({"x": "hello"}) == ["hello"]


def test_positional_multi_value_emits_inline():
    args = _args([{"name": "items", "positional": True, "multiple": True}])
    assert args.format_argv({"items": ["a", "b", "c"]}) == ["a", "b", "c"]


def test_option_emits_flag_and_value():
    args = _args([{"name": "out", "options": ["--out"]}])
    assert args.format_argv({"out": "build"}) == ["--out", "build"]


@pytest.mark.parametrize(
    ("options", "expected_flag"),
    [
        (["-o", "--out"], "-o"),
        (["--out", "-o"], "--out"),
    ],
)
def test_option_first_declared_name_wins(options, expected_flag):
    args = _args([{"name": "out", "options": options}])
    assert args.format_argv({"out": "build"}) == [expected_flag, "build"]


def test_option_multi_value_space_separated():
    args = _args([{"name": "files", "options": ["--files"], "multiple": True}])
    assert args.format_argv({"files": ["a", "b"]}) == ["--files", "a", "b"]


def test_option_multi_value_empty_omits_flag():
    args = _args([{"name": "files", "options": ["--files"], "multiple": True}])
    assert args.format_argv({"files": []}) == []


@pytest.mark.parametrize(
    ("default", "value", "expected"),
    [
        (False, False, []),
        (False, True, ["--flag"]),
        (True, True, []),
        (True, False, ["--flag"]),
    ],
)
def test_boolean_emit_iff_value_differs_from_default(default, value, expected):
    args = _args(
        [
            {
                "name": "flag",
                "options": ["--flag"],
                "type": "boolean",
                "default": default,
            }
        ]
    )
    assert args.format_argv({"flag": value}) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # Boolean declared with no explicit default — poe's parser treats
        # absent default as False (store_true action), so the "emit iff value
        # differs from default" rule must use that same coercion.
        (False, []),
        (True, ["--flag"]),
    ],
)
def test_boolean_without_explicit_default_treats_default_as_false(value, expected):
    args = _args([{"name": "flag", "options": ["--flag"], "type": "boolean"}])
    assert args.format_argv({"flag": value}) == expected


def test_integer_value_serialized_as_string():
    args = _args([{"name": "n", "options": ["-n"], "type": "integer"}])
    assert args.format_argv({"n": 42}) == ["-n", "42"]


def test_float_value_serialized_as_string():
    args = _args([{"name": "r", "options": ["-r"], "type": "float"}])
    assert args.format_argv({"r": 1.5}) == ["-r", "1.5"]


def test_omits_args_not_present_in_values():
    args = _args(
        [
            {"name": "x", "positional": True},
            {"name": "y", "options": ["--y"]},
        ]
    )
    assert args.format_argv({"x": "value"}) == ["value"]


def test_omits_options_with_none_value():
    args = _args([{"name": "out", "options": ["--out"]}])
    assert args.format_argv({"out": None}) == []


def test_preserves_declaration_order_for_positionals():
    args = _args(
        [
            {"name": "a", "positional": True},
            {"name": "b", "positional": True},
        ]
    )
    assert args.format_argv({"a": "1", "b": "2"}) == ["1", "2"]


def test_mixed_positional_and_option():
    args = _args(
        [
            {"name": "target", "positional": True},
            {"name": "out", "options": ["--out"]},
        ]
    )
    assert args.format_argv({"target": "alice", "out": "build"}) == [
        "alice",
        "--out",
        "build",
    ]
