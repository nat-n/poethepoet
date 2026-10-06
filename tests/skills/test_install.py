"""
Tests for the ``poe _install_skill`` builtin (poethepoet/skills/install.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from poethepoet.skills import install

BUNDLED_SKILL = Path(install.__file__).parent / "poethepoet"
BUNDLED_VERSION = (BUNDLED_SKILL / "version.txt").read_text().strip()


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """
    Run in an empty project dir with an empty home dir.
    """
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setattr(Path, "home", lambda: home)
    return project


@pytest.fixture
def answers(monkeypatch):
    """
    Feed the given answers to input(); raise EOFError once they run out.
    """

    def set_answers(*replies: str):
        remaining = list(replies)
        prompts: list[str] = []

        def fake_input(prompt: str = "") -> str:
            prompts.append(prompt)
            if not remaining:
                raise EOFError
            return remaining.pop(0)

        monkeypatch.setattr("builtins.input", fake_input)
        return prompts

    return set_answers


def run_cli(*args: str) -> int:
    try:
        install.main(args)
    except SystemExit as exit_:
        return int(exit_.code or 0)
    return 0


def test_fresh_install_copies_bundled_tree(workspace, answers):
    answers()
    assert run_cli("skills") == 0
    assert _tree(workspace / "skills" / "poethepoet") == _tree(BUNDLED_SKILL)


def test_upgrade_replaces_older_install_and_removes_stale_files(workspace, answers):
    answers()
    dest = workspace / "skills" / "poethepoet"
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("old")
    (dest / "version.txt").write_text("0.1.0")
    (dest / "stale.md").write_text("stale")

    assert run_cli("skills", "--upgrade") == 0
    assert _tree(dest) == _tree(BUNDLED_SKILL)


@pytest.mark.parametrize("installed_version", [BUNDLED_VERSION, "999.0.0"])
def test_upgrade_skips_same_or_newer_install(
    workspace, answers, capsys, installed_version
):
    answers()
    dest = workspace / "skills" / "poethepoet"
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("custom")
    (dest / "version.txt").write_text(installed_version)

    assert run_cli("skills", "-u") == 0
    assert (dest / "SKILL.md").read_text() == "custom"
    assert "skipping" in capsys.readouterr().out


def test_prompt_without_input_fails_cleanly(workspace, answers, capsys):
    """
    Agents and CI run without a TTY: a prompt must not raise a raw EOFError.
    """
    answers()
    (workspace / ".claude").mkdir()
    assert run_cli() == 1
    err = capsys.readouterr().err
    assert "No input available" in err
    assert "--upgrade" in err
    assert not (workspace / ".claude" / "skills").exists()


def test_reinstall_prompt_without_input_fails_cleanly(workspace, answers, capsys):
    answers()
    assert run_cli("skills") == 0
    assert run_cli("skills") == 1
    assert "No input available" in capsys.readouterr().err


def test_detected_dir_is_confirmed_interactively(workspace, answers):
    prompts = answers("")
    (workspace / ".claude").mkdir()
    assert run_cli() == 0
    assert ".claude" in prompts[0]
    assert (workspace / ".claude" / "skills" / "poethepoet" / "SKILL.md").is_file()


def test_relative_path_answer_is_used(workspace, answers):
    answers("other-skills")
    (workspace / ".codex").mkdir()
    assert run_cli() == 0
    assert (workspace / "other-skills" / "poethepoet" / "SKILL.md").is_file()


@pytest.mark.parametrize(
    ("markers", "expected"),
    [
        ([".claude", ".codex"], ".claude/skills"),
        ([".pi"], ".pi/skills"),
        ([".agents"], ".agents/skills"),
        (["~/.claude", "~/.agents"], "~/.claude/skills"),
        (["~/.pi/agent"], "~/.pi/agent/skills"),
        ([".codex", "~/.claude"], ".codex/skills"),
    ],
)
def test_detection_precedence(workspace, markers, expected):
    home = Path.home()
    for marker in markers:
        path = home / marker[2:] if marker.startswith("~/") else workspace / marker
        path.mkdir(parents=True)
    expected_path = (
        home / expected[2:] if expected.startswith("~/") else workspace / expected
    )
    assert install._detect_skills_dir() == expected_path.resolve()


def test_upgrade_without_detected_dir_fails(workspace, answers, capsys):
    answers()
    assert run_cli("--upgrade") == 1
    assert "Could not detect a skills directory" in capsys.readouterr().err


def test_symlinked_install_is_upgraded_in_place(workspace, answers):
    """
    Skill managers may symlink <skills>/poethepoet to a shared copy.
    """
    answers()
    shared = workspace / "shared" / "poethepoet"
    shared.mkdir(parents=True)
    (shared / "SKILL.md").write_text("old")
    (shared / "version.txt").write_text("0.1.0")
    skills = workspace / "skills"
    skills.mkdir()
    (skills / "poethepoet").symlink_to(shared, target_is_directory=True)

    assert run_cli("skills", "--upgrade") == 0
    assert (skills / "poethepoet").is_symlink()
    assert _tree(shared) == _tree(BUNDLED_SKILL)


def test_dangling_symlink_destination_fails_cleanly(workspace, answers, capsys):
    answers()
    skills = workspace / "skills"
    skills.mkdir()
    (skills / "poethepoet").symlink_to(workspace / "missing")
    assert run_cli("skills", "--upgrade") == 1
    assert "symlink" in capsys.readouterr().err


def test_file_destination_fails_cleanly(workspace, answers, capsys):
    answers()
    skills = workspace / "skills"
    skills.mkdir()
    (skills / "poethepoet").write_text("not a dir")
    assert run_cli("skills", "--upgrade") == 1
    assert "is not a directory" in capsys.readouterr().err
    assert (skills / "poethepoet").read_text() == "not a dir"


def test_unrelated_directory_is_not_overwritten(workspace, answers, capsys):
    answers()
    dest = workspace / "skills" / "poethepoet"
    dest.mkdir(parents=True)
    (dest / "notes.txt").write_text("mine")
    assert run_cli("skills", "--upgrade") == 1
    assert "doesn't contain an installed skill" in capsys.readouterr().err
    assert (dest / "notes.txt").read_text() == "mine"


def test_never_installs_over_the_bundled_skill(workspace, answers, capsys):
    answers()
    before = _tree(BUNDLED_SKILL)
    assert run_cli(str(BUNDLED_SKILL.parent), "--upgrade") == 1
    assert "overlaps the skill bundled with poe" in capsys.readouterr().err
    assert _tree(BUNDLED_SKILL) == before


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_flag_prints_usage(workspace, capsys, flag):
    assert run_cli(flag) == 0
    assert "poe _install_skill" in capsys.readouterr().out
    assert not (workspace / flag).exists()


def test_unknown_flag_is_rejected(workspace, capsys):
    assert run_cli("--bogus") == 2
    assert "unrecognized arguments" in capsys.readouterr().err
    assert list(workspace.iterdir()) == []


@pytest.mark.parametrize(
    ("installed", "bundled", "expected"),
    [
        ("0.48.0", "0.48.0", 0),
        ("0.47.1", "0.48.0", -1),
        ("0.49.0", "0.48.0", 1),
        ("0.48.0", "0.49.0rc1", -1),
        ("0.49.0rc1", "0.49.0", -1),
        ("0.49.0rc1", "0.49.0rc2", -1),
        ("0.49.0b1", "0.49.0rc1", -1),
        ("0.49.0.dev1", "0.49.0a1", -1),
        ("0.10.0", "0.9.0", 1),
        (None, "0.48.0", -1),
        ("garbage", "0.48.0", -1),
    ],
)
def test_compare_versions(installed, bundled, expected):
    assert install._compare_versions(installed, bundled) == expected


def test_builtin_dispatch_parses_args(workspace, monkeypatch, answers):
    from poethepoet import main

    answers()
    monkeypatch.setattr(sys, "argv", ["poe", "_install_skill", "skills", "-u"])
    main()
    assert (workspace / "skills" / "poethepoet" / "SKILL.md").is_file()
    assert not (workspace / "-u").exists()
