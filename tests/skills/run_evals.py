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


def read_project_files(project_dir: Path) -> str:
    """Read poe config files written by Claude during the eval."""
    parts = []
    for name in [
        "pyproject.toml",
        "poe_tasks.toml",
        "poe_tasks.yaml",
        "poe_tasks.json",
    ]:
        path = project_dir / name
        if path.exists():
            parts.append(f"# --- {name} ---\n{path.read_text()}")
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


def _check(text: str, expectation: str) -> dict[str, Any]:
    exp_lower = expectation.lower()

    # Ordered list of (trigger phrase, search term, description)
    heuristics: list[tuple[str, str]] = [
        ("$poe_extra_args", "$POE_EXTRA_ARGS"),
        ("parallel", "parallel"),
        ("sequence", "sequence"),
        ("help =", "help ="),
        ("poe test", "poe test"),
        ("poe --help", "poe"),
        ("`poe`", "poe"),
        ("uv run poe", "uv run poe"),
        ("uv add", "uv add"),
        ("script task", "script"),
        ("script =", "script ="),
        ("main function", ":main"),
        ("main(", ":main"),
        ("pythonpath", "PYTHONPATH"),
        ("args matching", "args"),
        ("defines a test task", "[tool.poe.tasks.test]"),
        ("defines a lint task", "[tool.poe.tasks.lint]"),
        ("defines a types task", "[tool.poe.tasks.types]"),
        ("defines a format task", "[tool.poe.tasks.format]"),
        ("defines a check task", "[tool.poe.tasks.check]"),
    ]

    for trigger, search in heuristics:
        if trigger in exp_lower:
            found = search in text
            status = "Found" if found else "Not found"
            return {
                "text": expectation,
                "passed": found,
                "evidence": f"{status} {search!r} in response",
            }

    return {
        "text": expectation,
        "passed": True,
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

        project_text = read_project_files(project_dir)
        if project_text:
            (out_dir / "project_files.txt").write_text(project_text)

        grade_text = response_text + "\n" + project_text
        expectations = eval_def.get("expectations", [])
        grades = grade(grade_text, expectations)
        n_passed = sum(1 for g in grades if g["passed"])

        grading: dict[str, Any] = {
            "expectations": grades,
            "summary": {
                "passed": n_passed,
                "failed": len(grades) - n_passed,
                "total": len(grades),
                "pass_rate": n_passed / len(grades) if grades else 1.0,
            },
        }
        (out_dir / "grading.json").write_text(json.dumps(grading, indent=2))

        if verbose:
            for g in grades:
                mark = "✓" if g["passed"] else "✗"
                print(f"      {mark} {g['text']}")
                print(f"        → {g['evidence']}")

        return {
            "eval_id": eval_def["id"],
            "with_skill": with_skill,
            "replica": replica,
            "passed": n_passed,
            "total": len(grades),
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
