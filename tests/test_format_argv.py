"""
Unit tests for ``PoeTaskArgs.format_argv`` — the inverse of ``parse``, used
when a module-style script task needs to forward declared args (with defaults
applied) into a ``python -m`` subprocess.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from poethepoet.env.cache import EnvFileCache
from poethepoet.env.task_env import TaskEnv
from poethepoet.exceptions import ConfigValidationError
from poethepoet.io import PoeIO
from poethepoet.task.args import PoeTaskArgs


def _args(args_def: Any) -> PoeTaskArgs:
    return PoeTaskArgs(args_def, "task", PoeIO(make_default=False))


def _env(env_vars: Mapping[str, str] | None = None) -> TaskEnv:
    """
    Minimal TaskEnv for unit tests. The format_argv tests never touch
    envfiles or lazy vars, so a stub cache is sufficient.
    """
    return TaskEnv(
        env=dict(env_vars or {}),
        args={},
        envfiles=EnvFileCache(Path.cwd(), PoeIO(make_default=False)),
        lazy_vars={},
        private_vars=set(),
    )


def test_positional_emits_value() -> None:
    args = _args([{"name": "x", "positional": True}])
    assert args.format_argv({"x": "hello"}, _env()) == ["hello"]


def test_positional_multi_value_emits_inline() -> None:
    args = _args([{"name": "items", "positional": True, "multiple": True}])
    assert args.format_argv({"items": ["a", "b", "c"]}, _env()) == ["a", "b", "c"]


def test_option_emits_flag_and_value() -> None:
    args = _args([{"name": "out", "options": ["--out"]}])
    assert args.format_argv({"out": "build"}, _env()) == ["--out", "build"]


@pytest.mark.parametrize(
    ("options", "expected_flag"),
    [
        (["-o", "--out"], "-o"),
        (["--out", "-o"], "--out"),
    ],
)
def test_option_first_declared_name_wins(
    options: list[str], expected_flag: str
) -> None:
    args = _args([{"name": "out", "options": options}])
    assert args.format_argv({"out": "build"}, _env()) == [expected_flag, "build"]


def test_option_multi_value_space_separated() -> None:
    args = _args([{"name": "files", "options": ["--files"], "multiple": True}])
    assert args.format_argv({"files": ["a", "b"]}, _env()) == ["--files", "a", "b"]


def test_option_multi_value_empty_omits_flag() -> None:
    args = _args([{"name": "files", "options": ["--files"], "multiple": True}])
    assert args.format_argv({"files": []}, _env()) == []


@pytest.mark.parametrize(
    ("default", "value", "expected"),
    [
        (False, False, []),
        (False, True, ["--flag"]),
        (True, True, []),
        (True, False, ["--flag"]),
    ],
)
def test_boolean_emit_iff_value_differs_from_default(
    default: bool, value: bool, expected: list[str]
) -> None:
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
    assert args.format_argv({"flag": value}, _env()) == expected


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
def test_boolean_without_explicit_default_treats_default_as_false(
    value: bool, expected: list[str]
) -> None:
    args = _args([{"name": "flag", "options": ["--flag"], "type": "boolean"}])
    assert args.format_argv({"flag": value}, _env()) == expected


@pytest.mark.parametrize(
    ("default_literal", "value", "expected"),
    [
        # String literals must coerce to the same bool the parser uses, so
        # "emit iff value != coerced(default)" holds regardless of how the
        # user spelled the default.
        ("true", True, []),
        ("true", False, ["--flag"]),
        ("True", True, []),
        ("1", True, []),
        ("t", True, []),
        ("false", False, []),
        ("false", True, ["--flag"]),
        ("False", False, []),
        ("FALSE", False, []),
        ("0", False, []),
        ("f", False, []),
        ("", False, []),
        ("  TRUE  ", True, []),
    ],
)
def test_boolean_string_default_coerced_for_emit_decision(
    default_literal: str, value: bool, expected: list[str]
) -> None:
    args = _args(
        [
            {
                "name": "flag",
                "options": ["--flag"],
                "type": "boolean",
                "default": default_literal,
            }
        ]
    )
    assert args.format_argv({"flag": value}, _env()) == expected


@pytest.mark.parametrize(
    ("template", "env_vars", "value", "expected"),
    [
        ("${BOOL_DEFAULT}", {"BOOL_DEFAULT": "true"}, True, []),
        ("${BOOL_DEFAULT}", {"BOOL_DEFAULT": "true"}, False, ["--flag"]),
        ("${BOOL_DEFAULT}", {"BOOL_DEFAULT": "false"}, False, []),
        ("${BOOL_DEFAULT}", {"BOOL_DEFAULT": "false"}, True, ["--flag"]),
        ("${BOOL_DEFAULT}", {"BOOL_DEFAULT": ""}, False, []),
    ],
)
def test_boolean_templated_default_resolved_via_env(
    template: str, env_vars: dict[str, str], value: bool, expected: list[str]
) -> None:
    args = _args(
        [
            {
                "name": "flag",
                "options": ["--flag"],
                "type": "boolean",
                "default": template,
            }
        ]
    )
    assert args.format_argv({"flag": value}, _env(env_vars)) == expected


def test_boolean_templated_default_resolving_to_garbage_raises() -> None:
    args = _args(
        [
            {
                "name": "flag",
                "options": ["--flag"],
                "type": "boolean",
                "default": "${BOOL_DEFAULT}",
            }
        ]
    )
    with pytest.raises(ConfigValidationError, match="Cannot interpret"):
        args.format_argv({"flag": False}, _env({"BOOL_DEFAULT": "maybe"}))


@pytest.mark.parametrize(
    "default_value",
    [True, False, "true", "TRUE", "false", "0", "1", "t", "f", "", "  TRUE  "],
)
def test_validator_accepts_recognised_boolean_defaults(default_value: Any) -> None:
    _args(
        [
            {
                "name": "flag",
                "options": ["--flag"],
                "type": "boolean",
                "default": default_value,
            }
        ]
    )


@pytest.mark.parametrize("default_value", ["yes", "no", "maybe", "2", "off", "on"])
def test_validator_rejects_unrecognised_boolean_string_defaults(
    default_value: str,
) -> None:
    with pytest.raises(ConfigValidationError, match="Cannot interpret"):
        _args(
            [
                {
                    "name": "flag",
                    "options": ["--flag"],
                    "type": "boolean",
                    "default": default_value,
                }
            ]
        )


def test_validator_defers_templated_boolean_default_to_runtime() -> None:
    # Template-shaped strings can only be checked once a TaskEnv is in scope,
    # so the validator lets them through.
    _args(
        [
            {
                "name": "flag",
                "options": ["--flag"],
                "type": "boolean",
                "default": "${BOOL_DEFAULT}",
            }
        ]
    )


def test_integer_value_serialized_as_string() -> None:
    args = _args([{"name": "n", "options": ["-n"], "type": "integer"}])
    assert args.format_argv({"n": 42}, _env()) == ["-n", "42"]


def test_float_value_serialized_as_string() -> None:
    args = _args([{"name": "r", "options": ["-r"], "type": "float"}])
    assert args.format_argv({"r": 1.5}, _env()) == ["-r", "1.5"]


def test_omits_args_not_present_in_values() -> None:
    args = _args(
        [
            {"name": "x", "positional": True},
            {"name": "y", "options": ["--y"]},
        ]
    )
    assert args.format_argv({"x": "value"}, _env()) == ["value"]


def test_omits_options_with_none_value() -> None:
    args = _args([{"name": "out", "options": ["--out"]}])
    assert args.format_argv({"out": None}, _env()) == []


def test_preserves_declaration_order_for_positionals() -> None:
    args = _args(
        [
            {"name": "a", "positional": True},
            {"name": "b", "positional": True},
        ]
    )
    assert args.format_argv({"a": "1", "b": "2"}, _env()) == ["1", "2"]


def test_mixed_positional_and_option() -> None:
    args = _args(
        [
            {"name": "target", "positional": True},
            {"name": "out", "options": ["--out"]},
        ]
    )
    assert args.format_argv({"target": "alice", "out": "build"}, _env()) == [
        "alice",
        "--out",
        "build",
    ]
