"""Eval runner for the poethepoet agent skill.

Run via poe:
    poe eval-skill
    poe eval-skill --eval 1 --eval 3
    poe eval-skill --replicas 3 --no-baseline
    poe eval-skill --model claude-opus-4-7

Or directly (with PYTHONPATH set):
    python tests/skills/run_evals.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_HERE = Path(__file__).parent
_PROJECT_ROOT = _HERE.parent.parent
_SKILL_PATH = _PROJECT_ROOT / "poethepoet" / "skills" / "poethepoet"
_EVALS_PATH = _HERE / "evals.json"
_FIXTURES_PATH = _HERE / "fixtures"
_RESULTS_DIR = _HERE / "results"


# ---------------------------------------------------------------------------
# Project setup
# ---------------------------------------------------------------------------


def setup_project(fixture: str, install_skill: bool) -> Path:
    """
    Copy a fixture project to a fresh temp directory and optionally install
    the skill into its .claude/skills/ so claude -p can discover it.
    """
    tmp = Path(tempfile.mkdtemp(prefix="poe_eval_"))
    src = _FIXTURES_PATH / fixture
    dest = tmp / "project"

    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        dest.mkdir(parents=True)

    if install_skill:
        skill_dest = dest / ".claude" / "skills" / "poethepoet"
        skill_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(_SKILL_PATH, skill_dest)

    return dest


def teardown_project(project_dir: Path) -> None:
    shutil.rmtree(project_dir.parent, ignore_errors=True)


# ---------------------------------------------------------------------------
# Claude invocation
# ---------------------------------------------------------------------------


def run_claude(prompt: str, cwd: Path, model: str | None = None) -> dict[str, Any]:
    """
    Run ``claude -p <prompt>`` in *cwd* and return the parsed JSON result.

    Strips CLAUDECODE from the environment so claude -p can be called from
    inside an existing Claude Code session without conflict.
    """
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--permission-mode",
        "bypassPermissions",
        # Skip user-level settings so the eval runs against a clean baseline
        # (otherwise the caller's output style, hooks, env, etc. leak into the
        # subprocess and confound results). Project + local sources still apply
        # so the skill installed at the fixture's .claude/skills/ is discovered.
        "--setting-sources",
        "project,local",
    ]
    if model:
        cmd.extend(["--model", model])

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"result": "", "error": "timed out after 300s"}

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"result": result.stdout, "error": result.stderr or "non-JSON output"}


# ---------------------------------------------------------------------------
# Project file reading
# ---------------------------------------------------------------------------


def read_project_files(project_dir: Path, fixture: str | None = None) -> str:
    """
    Read poe config files written by Claude during the eval.

    If *fixture* is given, files identical to the fixture's copy are left out,
    so that grading only sees what the agent changed (otherwise content already
    in the fixture, like `help =` lines, satisfies expectations by itself).
    """
    parts = []
    for name in [
        "pyproject.toml",
        "poe_tasks.toml",
        "poe_tasks.yaml",
        "poe_tasks.json",
    ]:
        path = project_dir / name
        if not path.exists():
            continue
        content = path.read_text()
        original = _FIXTURES_PATH / fixture / name if fixture else None
        if original and original.exists() and original.read_text() == content:
            continue
        parts.append(f"# --- {name} ---\n{content}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------


def grade(response_text: str, expectations: list[str]) -> list[dict[str, Any]]:
    """
    Grade *response_text* against each expectation string.

    Expectations are plain English; grading uses keyword heuristics where
    possible and falls back to "manual review required" for anything
    qualitative.
    """
    return [_check(response_text, exp) for exp in expectations]


_COUNTER_EXAMPLE_MARKERS = (
    "wrong",
    "broken",
    "❌",
    "don't",
    "do not",
    "avoid",
    "incorrect",
    "fails silently",
    "not recommended",
)

# How many preceding lines to scan (in addition to the matched line) when
# looking for a counter-example marker. A label like ``# Wrong`` or ``❌ broken``
# is usually a comment or prose line *above* the offending value rather than on
# the same line — e.g. a ``# Wrong`` comment sitting above a
# ``[tool.poe.tasks.x]`` header which in turn sits above the value.
_COUNTER_EXAMPLE_LOOKBACK = 3


def _is_labeled_counter_example(text: str, search: str | re.Pattern) -> bool:
    """
    Return True if every occurrence of *search* in *text* falls within a window
    (the matched line plus the few preceding lines) that contains a
    counter-example marker (e.g. "wrong", "broken", "❌"). Used by negate-mode
    heuristics to avoid penalising responses that present the forbidden pattern
    as an explicit ❌-labelled contrast rather than as a recommendation.

    The window reaches back over preceding lines because the label is commonly
    above the code, not on the same line (see ``_COUNTER_EXAMPLE_LOOKBACK``).

    Conservative: a single un-labelled occurrence means False (recommendation).

    *search* is a literal string (a leading newline is ignored) or a compiled
    regular expression.
    """
    lines = text.splitlines()
    if isinstance(search, re.Pattern):
        positions = [match.start() for match in search.finditer(text)]
    else:
        positions = [
            match.start() for match in re.finditer(re.escape(search.lstrip("\n")), text)
        ]
    for pos in positions:
        line_no = text.count("\n", 0, pos)
        window = "\n".join(
            lines[max(0, line_no - _COUNTER_EXAMPLE_LOOKBACK) : line_no + 1]
        ).lower()
        if not any(marker in window for marker in _COUNTER_EXAMPLE_MARKERS):
            return False
    return bool(positions)


def _contains(text: str, search: str | re.Pattern) -> bool:
    if isinstance(search, re.Pattern):
        return search.search(text) is not None
    return search in text


def _task_defined(name: str) -> re.Pattern:
    """
    Match a definition of task *name* in TOML, as a table header or as a key.
    """
    escaped = re.escape(name)
    return re.compile(
        rf"^\s*(\[tool\.poe\.tasks\.{escaped}\]|\[tasks\.{escaped}\]|{escaped}\s*=)",
        re.MULTILINE,
    )


def _check(text: str, expectation: str) -> dict[str, Any]:
    exp_lower = expectation.lower()

    # Each entry is (trigger, search) — passes when `search` (a string or a
    # compiled regex) is found in `text`, or (trigger, search, "negate") —
    # passes when `search` is NOT found (catches "Response does not X" style
    # expectations by detecting the forbidden pattern). First matching trigger
    # wins. Expectations matching no trigger need manual review.
    heuristics: list[tuple] = [
        ("$poe_extra_args", "$POE_EXTRA_ARGS"),
        ("`parallel`", re.compile(r"\bparallel\s*=")),
        ("`sequence`", re.compile(r"\bsequence\s*=")),
        ("help =", "help ="),
        ("poe test", "poe test"),
        (
            "poe --help",
            re.compile(r"(`poe`|`poe --help`|^\s*\$?\s*poe\s*$)", re.MULTILINE),
        ),
        ("-k config", "-k config"),
        ("lint task definition", _task_defined("lint")),
        ("uv run poe", "uv run poe"),
        ("uv add", "uv add"),
        ("script task", "script ="),
        ("script =", "script ="),
        ("main function", ":main"),
        ("main(", ":main"),
        ("pythonpath", "PYTHONPATH"),
        (
            "args matching",
            re.compile(
                r"^\s*(\[\[tool\.poe\.tasks\.[\w-]+\.args\]\]|args\s*=)", re.MULTILINE
            ),
        ),
        ("defines a test task", _task_defined("test")),
        ("defines a lint task", _task_defined("lint")),
        ("defines a types task", _task_defined("types")),
        ("defines a format task", _task_defined("format")),
        ("defines a check task", _task_defined("check")),
        # Negative heuristics — pass when the forbidden pattern is NOT present.
        # The leading "\n" requires the pattern to be on its own line (typical
        # of an agent's recommended TOML block) so inline prose discussions of
        # the wrong form (e.g. "don't write `control.expr = \"${_target}\"`")
        # don't false-fail correct responses.
        #
        # Eval 2: `--` is forwarded literally to a task without declared args.
        ("poe lint -- --fix", "poe lint -- --fix", "negate"),
        # Eval 6: agent must not recommend wrapping ${VAR} in quotes inside an expr.
        ("without extra quoting", "\nexpr = \"'${STAGE}'\"", "negate"),
        ("does not recommend wrapping", "\nexpr = \"'${STAGE}'\"", "negate"),
        # Eval 7: control expr should use the bare arg name (typed value), not
        # the ${...} env-string form; matches dotted and inline-table forms.
        (
            "bare-variable form",
            re.compile(r'\bexpr\s*=\s*"\$\{_target\}"'),
            "negate",
        ),
        (
            "not on individual case tasks",
            re.compile(r"\[\[[\w.-]+\.switch\]\][^\[]*?\n\s*args\s*="),
            "negate",
        ),
    ]

    for entry in heuristics:
        trigger, search = entry[0], entry[1]
        negate = len(entry) > 2 and entry[2] == "negate"
        if trigger in exp_lower:
            found = _contains(text, search)
            if negate and found and _is_labeled_counter_example(text, search):
                # The forbidden pattern appears as an explicit ❌/broken/wrong
                # counter-example (often shown next to the ✅ form to teach the
                # contrast). That's the gold-standard didactic answer, not a
                # genuine recommendation — pass.
                return {
                    "text": expectation,
                    "passed": True,
                    "evidence": (
                        f"Forbidden pattern {search!r} present but labeled "
                        f"as a counter-example (wrong/broken/❌/don't)"
                    ),
                }
            passed = (not found) if negate else found
            if negate:
                status = (
                    f"Forbidden pattern {search!r} not in response"
                    if not found
                    else f"Forbidden pattern {search!r} found in response"
                )
            else:
                status = (
                    f"Found {search!r} in response"
                    if found
                    else f"Not found {search!r} in response"
                )
            return {
                "text": expectation,
                "passed": passed,
                "evidence": status,
            }

    return {
        "text": expectation,
        "passed": None,
        "evidence": "No programmatic check available — requires manual review",
    }


# ---------------------------------------------------------------------------
# Single eval run
# ---------------------------------------------------------------------------


def run_one(
    eval_def: dict[str, Any],
    with_skill: bool,
    replica: int,
    model: str | None,
    results_dir: Path,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run one eval scenario and write output/grading to *results_dir*."""
    fixture = eval_def.get("fixture", "poe_project")
    project_dir = setup_project(fixture, install_skill=with_skill)

    label = "with_skill" if with_skill else "without_skill"
    out_dir = results_dir / f"eval-{eval_def['id']}" / label
    if replica > 1:
        out_dir = out_dir / f"replica-{replica}"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        response = run_claude(eval_def["prompt"], project_dir, model=model)
        response_text = response.get("result", "") or ""

        (out_dir / "response.json").write_text(json.dumps(response, indent=2))

        project_text = read_project_files(project_dir, fixture)
        if project_text:
            (out_dir / "project_files.txt").write_text(project_text)

        grade_text = response_text + "\n" + project_text
        expectations = eval_def.get("expectations", [])
        grades = grade(grade_text, expectations)
        # Expectations without a programmatic check (passed is None) need manual
        # review and are left out of the pass rate.
        checked = [g for g in grades if g["passed"] is not None]
        n_passed = sum(1 for g in checked if g["passed"])

        grading: dict[str, Any] = {
            "expectations": grades,
            "summary": {
                "passed": n_passed,
                "failed": len(checked) - n_passed,
                "manual": len(grades) - len(checked),
                "total": len(checked),
                "pass_rate": n_passed / len(checked) if checked else 1.0,
            },
        }
        (out_dir / "grading.json").write_text(json.dumps(grading, indent=2))

        if verbose:
            for g in grades:
                mark = {True: "✓", False: "✗", None: "?"}[g["passed"]]
                print(f"      {mark} {g['text']}")
                print(f"        → {g['evidence']}")

        return {
            "eval_id": eval_def["id"],
            "with_skill": with_skill,
            "replica": replica,
            "passed": n_passed,
            "total": len(checked),
            "error": response.get("error"),
        }
    finally:
        teardown_project(project_dir)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main(
    evals: list[int] | None = None,
    replicas: int = 1,
    no_baseline: bool = False,
    model: str | None = None,
    verbose: bool = False,
) -> None:
    """
    Run poethepoet skill evals.

    Args:
        evals: Specific eval IDs to run (default: all)
        replicas: Number of independent runs per eval per configuration
        no_baseline: Skip without-skill baseline runs
        model: Claude model to use (default: your configured model)
        verbose: Print per-expectation results with evidence
    """
    evals_data = json.loads(_EVALS_PATH.read_text())
    eval_list: list[dict[str, Any]] = evals_data["evals"]

    if evals:
        eval_list = [e for e in eval_list if e["id"] in evals]

    if not eval_list:
        print(f"No evals matched (requested IDs: {evals})", file=sys.stderr)
        sys.exit(1)

    _RESULTS_DIR.mkdir(exist_ok=True)

    configs = [True] + ([] if no_baseline else [False])
    all_results: list[dict[str, Any]] = []

    for eval_def in eval_list:
        for with_skill in configs:
            for replica in range(1, replicas + 1):
                label = "with skill   " if with_skill else "without skill"
                rep_tag = f" replica {replica}/{replicas}" if replicas > 1 else ""
                print(f"  eval {eval_def['id']}  {label}{rep_tag} ...", flush=True)

                result = run_one(
                    eval_def, with_skill, replica, model, _RESULTS_DIR, verbose
                )
                all_results.append(result)

                passed = result["passed"]
                total = result["total"]
                err = f"  ⚠ {result['error'][:70]}" if result.get("error") else ""
                mark = "✓" if passed == total else "✗"
                print(f"  {mark} {passed}/{total} assertions passed{err}")

    # Summary table
    print("\n── Summary ─────────────────────────────────────────")
    for r in all_results:
        label = "with skill   " if r["with_skill"] else "without skill"
        rep = f" r{r['replica']}" if replicas > 1 else ""
        mark = "✓" if r["passed"] == r["total"] else "✗"
        print(
            f"  {mark}  eval-{r['eval_id']}  {label}{rep}  {r['passed']}/{r['total']}"
        )

    total_passed = sum(r["passed"] for r in all_results)
    total_checks = sum(r["total"] for r in all_results)
    print(f"\n  {total_passed}/{total_checks} total assertions passed")
    print(f"  Results written to {_RESULTS_DIR.relative_to(_PROJECT_ROOT)}/")

    if total_passed < total_checks:
        sys.exit(1)


if __name__ == "__main__":
    main()
