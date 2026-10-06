"""
Check that every TOML example in the bundled Agent Skill is valid poe config.

Agents copy these snippets verbatim, so a snippet that poe rejects is a bug in
the skill. Each ```toml block from SKILL.md and references/*.md is written to a
temporary project, loaded with PoeConfig, and every task is validated the same
way ``poe`` does on startup. Script call expressions and expr expressions are
also parsed, since poe only checks those when the task runs.

Snippets that are deliberately not loadable on their own (e.g. a block showing
alternative values for the same key) are listed in SKIPPED_SNIPPETS with the
reason, keyed by a substring that identifies the block.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

SKILL_DIR = Path(__file__).parents[2] / "poethepoet" / "skills" / "poethepoet"
SKILL_FILES = [SKILL_DIR / "SKILL.md", *sorted((SKILL_DIR / "references").glob("*.md"))]

# (file name, substring unique to the block) -> reason the block is not loadable
SKIPPED_SNIPPETS: dict[tuple[str, str], str] = {
    ("creating-tasks.md", 'cmd = "ty check"'): (
        "shows two alternative definitions of the same task"
    ),
    ("creating-tasks.md", 'shell = "poe test && poe build"'): (
        "contrasts a wrong and a right definition of the same task"
    ),
    ("task-options.md", 'optional = ["local.env"]  # silently'): (
        "shows alternative forms of the envfile option"
    ),
    ("task-options.md", 'executor = "simple"   # run without'): (
        "shows alternative forms of the executor option"
    ),
    ("task-options.md", "ignore_fail = [1, 2]"): (
        "shows alternative forms of the ignore_fail option"
    ),
    ("task-packages.md", '[tool.poe]\ninclude_script = "poethepoet_tasks:tasks"'): (
        "needs the poethepoet-tasks package installed"
    ),
    ("task-packages.md", "exclude_tags=['black']"): (
        "needs the poethepoet-tasks package installed"
    ),
    ("task-packages.md", 'RUFF_CONFIG = "path/to/ruff.toml"'): (
        "needs the poethepoet-tasks package installed"
    ),
    ("task-packages.md", 'include_script = "tasks:tasks()"'): (
        "needs the tasks.py module shown alongside it"
    ),
    ("task-packages.md", 'include_script = "my_tasks:tasks"'): (
        "needs the my_tasks package shown alongside it"
    ),
    ("creating-tasks.md", 'include = "tasks/common.toml"'): (
        "needs the included file shown alongside it"
    ),
    ("creating-tasks.md", 'include = ["tasks/backend.toml"'): (
        "needs the included files"
    ),
    ("creating-tasks.md", 'path = "frontend/pyproject.toml"'): (
        "needs the included subproject"
    ),
}

# Tasks that snippets commonly reference without defining. A stub is added for
# each one the snippet doesn't define itself, so references resolve.
STUB_TASK_NAMES = (
    "build",
    "build-backend",
    "build-frontend",
    "lint",
    "mypy",
    "pylint",
    "pytest",
    "test",
    "test-py310",
    "test-py311",
    "types",
    "_publish",
)

# A task table with none of these keys only shows options for a task, so it is
# given placeholder content
TASK_TYPE_KEYS = {
    "cmd",
    "script",
    "shell",
    "expr",
    "ref",
    "sequence",
    "parallel",
    "switch",
}


def _extract_toml_blocks() -> list[tuple[str, int, str]]:
    """
    Return (file name, line number, content) for every ```toml block in the skill.
    """
    blocks = []
    for path in SKILL_FILES:
        lines = path.read_text().splitlines()
        index = 0
        while index < len(lines):
            if lines[index].strip() == "```toml":
                start = index + 1
                end = start
                while lines[end].strip() != "```":
                    end += 1
                blocks.append((path.name, start + 1, "\n".join(lines[start:end])))
                index = end
            index += 1
    return blocks


TOML_BLOCKS = _extract_toml_blocks()


def _skip_reason(file_name: str, content: str) -> str | None:
    for (skip_file, marker), reason in SKIPPED_SNIPPETS.items():
        if skip_file == file_name and marker in content + "\n":
            return reason
    return None


def _defined_task_names(poe_table: dict[str, Any]) -> set[str]:
    names = set(poe_table.get("tasks", {}))
    for group in poe_table.get("groups", {}).values():
        names.update(group.get("tasks", {}))
    return names


def _build_project(content: str, project_dir: Path) -> Path:
    """
    Write the poe config from the snippet into project_dir as poe_tasks.json and
    return its path.

    Fragments of a task definition are wrapped in a task, tasks that a snippet
    only shows options for get placeholder content, and stub tasks are added
    for commonly referenced task names that the snippet doesn't define.
    """
    parsed = tomllib.loads(content)

    if "tool" in parsed:
        poe_table = parsed["tool"].get("poe", {})
    elif "tasks" in parsed or "groups" in parsed:
        poe_table = parsed
    else:
        poe_table = {"tasks": {"snippet": parsed}}

    task_tables = [poe_table.get("tasks", {})] + [
        group.get("tasks", {}) for group in poe_table.get("groups", {}).values()
    ]
    for tasks in task_tables:
        for task_def in tasks.values():
            if isinstance(task_def, dict) and not TASK_TYPE_KEYS & set(task_def):
                task_def["cmd"] = "echo snippet"

    defined = _defined_task_names(poe_table)
    tasks = poe_table.setdefault("tasks", {})
    for name in STUB_TASK_NAMES:
        if name not in defined:
            tasks[name] = f"echo {name}"

    config_path = project_dir / "poe_tasks.json"
    config_path.write_text(json.dumps(poe_table, indent=2))
    return config_path


def _arg_names(args_def: Any) -> set[str]:
    from poethepoet.task.args import ArgSpec

    if not args_def:
        return set()
    return {item["name"] for item in ArgSpec.normalize(args_def)}


def _check_python_content(spec: Any, inherited_args: set[str] = frozenset()) -> None:
    """
    Parse script call expressions and expr content the way poe does at runtime.
    """
    from poethepoet.helpers.python import resolve_expression
    from poethepoet.helpers.script import parse_script_reference

    arg_names = inherited_args | _arg_names(spec.options.get("args"))
    task_key = spec.task_type.__key__

    if task_key == "script" and ":" in spec.content:
        parse_script_reference(
            spec.content,
            dict.fromkeys(arg_names),
            allowed_vars={"sys", "os", "environ", "_dry_run"},
        )
    elif task_key == "expr":
        source = re.sub(r"\$\{(\w+)[^}]*\}", r"__env.\1", spec.content.strip())
        resolve_expression(
            source=source,
            arguments=arg_names,
            allowed_vars={"sys", "__env", *(spec.options.get("imports") or ())},
        )
    elif task_key == "switch":
        _check_python_content(spec.control_task_spec, arg_names)


@pytest.mark.parametrize(
    ("file_name", "line", "content"),
    TOML_BLOCKS,
    ids=[f"{file_name}:{line}" for file_name, line, _ in TOML_BLOCKS],
)
def test_skill_toml_snippet_is_valid_poe_config(
    file_name: str, line: int, content: str, tmp_path: Path
):
    from poethepoet.config import PoeConfig
    from poethepoet.task.base import TaskSpecFactory

    if reason := _skip_reason(file_name, content):
        pytest.skip(reason)

    config_path = _build_project(content, tmp_path)

    config = PoeConfig(cwd=tmp_path)
    config.load_sync(strict=True)
    factory = TaskSpecFactory(config)
    for spec in factory.load_all():
        spec.validate(config, factory)
        _check_python_content(spec)

    assert config.task_names, f"No tasks loaded from:\n{config_path.read_text()}"


def test_skipped_snippets_each_match_one_block():
    """
    Stale or ambiguous skip entries would silently hide future snippets.
    """
    for (skip_file, marker), reason in SKIPPED_SNIPPETS.items():
        matches = [
            line
            for file_name, line, content in TOML_BLOCKS
            if file_name == skip_file and marker in content + "\n"
        ]
        assert len(matches) == 1, (
            f"Skip entry {(skip_file, marker)!r} ({reason}) should match exactly one "
            f"toml block, but matched lines {matches}"
        )
