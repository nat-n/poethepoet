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

from run_evals import _check, _is_labeled_counter_example

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


# Eval 11 expectations, verbatim from evals.json.
EXP_PROJECT_REF = "Response defines tasks using `ref` with a `project` option"
EXP_NO_POE_C = (
    "Response does not use `poe -C` (or `poe --directory`) "
    "inside a `cmd` or `shell` task"
)
EXP_COMPOSED = (
    "Response composes the per-package refs with `sequence` or `parallel`, "
    "either as inline `{ ref, project }` items or as string refs to a generic "
    "task with a project arg"
)

REF_PROJECT_CONFIG = (
    "# --- pyproject.toml ---\n"
    "[tool.poe.tasks.check-all]\n"
    "sequence = [\n"
    '  { ref = "check", project = "packages/api" },\n'
    '  { ref = "check", project = "packages/web" },\n'
    "]\n"
)


def test_composition_passes_for_sequence_only_answer():
    result = _check("Use a sequence of refs.", EXP_COMPOSED)
    assert result["passed"] is True


def test_composition_passes_for_parallel_only_answer():
    result = _check("Use a parallel block of refs.", EXP_COMPOSED)
    assert result["passed"] is True


def test_composition_fails_for_answer_with_neither():
    result = _check("Loop over the packages in a script.", EXP_COMPOSED)
    assert result["passed"] is False


def test_poe_c_in_written_shell_task_fails():
    text = (
        "I added a check-all task.\n"
        "# --- pyproject.toml ---\n"
        "[tool.poe.tasks.check-all]\n"
        'shell = """\n'
        "for pkg in packages/*/; do\n"
        '  poe -C "$pkg" check\n'
        "done\n"
        '"""\n'
    )
    result = _check(text, EXP_NO_POE_C)
    assert result["passed"] is False


def test_poe_c_in_prose_only_passes():
    text = (
        "Instead of `poe -C packages/api check`, use ref with project.\n"
        + REF_PROJECT_CONFIG
    )
    result = _check(text, EXP_NO_POE_C)
    assert result["passed"] is True


def test_poe_directory_in_written_config_fails():
    text = '# --- pyproject.toml ---\n[tool.poe.tasks]\nx.cmd = "poe --directory a b"\n'
    result = _check(text, EXP_NO_POE_C)
    assert result["passed"] is False


def test_project_option_present_passes():
    result = _check(REF_PROJECT_CONFIG, EXP_PROJECT_REF)
    assert result["passed"] is True


def test_project_option_missing_fails():
    text = '# --- pyproject.toml ---\n[tool.poe.tasks]\ncheck-all.sequence = ["a"]\n'
    result = _check(text, EXP_PROJECT_REF)
    assert result["passed"] is False
