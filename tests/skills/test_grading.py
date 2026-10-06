"""
Unit tests for the eval-runner grading heuristics in ``run_evals.py``.

These guard the counter-example detection used by negate-mode assertions: a
correct didactic answer that shows a forbidden pattern as a labelled
``# Wrong`` contrast must not be penalised, while a genuine recommendation of
the forbidden pattern must still fail.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from run_evals import _check, _is_labeled_counter_example, grade, read_project_files

# The forbidden pattern used by eval-6's negate assertions (on its own line).
FORBIDDEN = "\nexpr = \"'${STAGE}'\""


def test_label_on_preceding_line_is_exempt():
    """
    A ``# Wrong`` label two lines above the value (with a table header in
    between) is the real ✅/❌ contrast shape, and must count as labelled.

    This is the eval-6 regression: the old same-line-only check false-failed it.
    """
    text = (
        "```toml\n"
        "# Correct\n"
        "[tool.poe.tasks.show]\n"
        'expr = "${STAGE}"\n'
        "\n"
        "# Wrong — yields the literal string\n"
        "[tool.poe.tasks.show]\n"
        "expr = \"'${STAGE}'\"\n"
        "```\n"
    )
    assert _is_labeled_counter_example(text, FORBIDDEN) is True


def test_same_line_label_is_exempt():
    text = "expr = \"'${STAGE}'\"  # ❌ broken\n"
    assert _is_labeled_counter_example(text, FORBIDDEN) is True


def test_unlabelled_recommendation_is_not_exempt():
    text = "Use this:\n```toml\nexpr = \"'${STAGE}'\"\n```\n"
    assert _is_labeled_counter_example(text, FORBIDDEN) is False


def test_marker_too_far_above_is_not_exempt():
    """A marker beyond the lookback window must not exempt the occurrence."""
    text = "# Wrong\nfiller one\nfiller two\nfiller three\nexpr = \"'${STAGE}'\"\n"
    assert _is_labeled_counter_example(text, FORBIDDEN) is False


def test_negate_assertion_passes_for_labelled_didactic_answer():
    """End-to-end via ``_check``: mirrors eval-6's correct with-skill answer."""
    response = (
        'No — use `expr = "${STAGE}"` (unquoted).\n\n'
        "```toml\n"
        "# Correct\n"
        'expr = "${STAGE}"\n'
        '# Wrong — yields the literal string "__env.STAGE"\n'
        "expr = \"'${STAGE}'\"\n"
        "```\n"
    )
    result = _check(
        response,
        "Response does not recommend wrapping the reference in quotes as a fix",
    )
    assert result["passed"] is True


def _expectations(eval_id: int) -> list[str]:
    evals = json.loads((Path(__file__).parent / "evals.json").read_text())["evals"]
    return next(item["expectations"] for item in evals if item["id"] == eval_id)


def test_refusal_does_not_pass_checked_expectations():
    """
    A refusal must not satisfy any positive programmatic check for evals 2 and 3
    (negative "does not" checks trivially pass).
    """
    for eval_id in (2, 3):
        results = grade("I can't help with that.", _expectations(eval_id))
        positive = [
            result
            for result in results
            if not result["text"].startswith("Response does not")
        ]
        assert not any(result["passed"] is True for result in positive), (
            eval_id,
            results,
        )


def test_unmatched_expectation_needs_manual_review():
    result = _check("anything", "Response explains something qualitative")
    assert result["passed"] is None


def test_inline_control_with_env_template_fails_eval_7():
    response = (
        "```toml\n"
        "[tool.poe.tasks.deploy]\n"
        'control = { expr = "${_target}" }\n'
        'args = [{ name = "_target", positional = true }]\n'
        "```\n"
    )
    results = grade(response, _expectations(7))
    assert results[0]["passed"] is False


def test_args_on_case_task_fails_eval_7():
    response = (
        "```toml\n"
        "[tool.poe.tasks.deploy]\n"
        'control.expr = "_target"\n'
        "\n"
        "[[tool.poe.tasks.deploy.switch]]\n"
        'case = "dev"\n'
        'cmd = "deploy dev"\n'
        'args = ["_target"]\n'
        "```\n"
    )
    results = grade(response, _expectations(7))
    assert results[0]["passed"] is True
    assert results[1]["passed"] is False


def test_lint_dash_dash_fix_fails_eval_2():
    response = (
        "```toml\n"
        "[tool.poe.tasks.lint]\n"
        'cmd = "ruff check ."\n'
        'help = "Lint"\n'
        "```\n"
        "Then run `poe lint -- --fix`.\n"
    )
    results = grade(response, _expectations(2))
    assert [result["passed"] for result in results] == [True, None, True, False]


def test_unchanged_fixture_files_are_not_graded(tmp_path):
    project = tmp_path / "project"
    shutil.copytree(Path(__file__).parent / "fixtures" / "uv_with_test", project)
    assert read_project_files(project, "uv_with_test") == ""
    with (project / "pyproject.toml").open("a") as config_file:
        config_file.write('\n[tool.poe.tasks.lint]\ncmd = "ruff check ."\n')
    assert "tool.poe.tasks.lint" in read_project_files(project, "uv_with_test")
