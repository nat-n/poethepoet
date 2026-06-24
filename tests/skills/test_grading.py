"""
Unit tests for the eval-runner grading heuristics in ``run_evals.py``.

These guard the counter-example detection used by negate-mode assertions: a
correct didactic answer that shows a forbidden pattern as a labelled
``# Wrong`` contrast must not be penalised, while a genuine recommendation of
the forbidden pattern must still fail.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from run_evals import _check, _is_labeled_counter_example  # noqa: E402

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
    text = (
        "# Wrong\n"
        "filler one\n"
        "filler two\n"
        "filler three\n"
        "expr = \"'${STAGE}'\"\n"
    )
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
