from __future__ import annotations

import shutil
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING

from ..__version__ import __version__

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable


def install_skill(skills_dir: Path | None = None, upgrade: bool = False) -> None:
    """
    Install or upgrade the bundled agent skill to a skills directory.

    CLI: poe _install_skill [<skills-dir>] [--upgrade]

    skills_dir: Parent directory for skills (skill installed at <dir>/poethepoet/).
                If None, auto-detects a suitable default and prompts to confirm.
    upgrade:    Non-interactive — overwrite if installed version is older;
                skip if equal or newer (never downgrades).
    """
    if skills_dir is not None:
        dest = skills_dir.expanduser().resolve() / "poethepoet"
    else:
        detected = _detect_skills_dir()
        if upgrade:
            if detected is None:
                print(
                    "Could not detect a skills directory. "
                    "Provide a path: poe _install_skill <skills-dir> --upgrade"
                )
                raise SystemExit(1)
            dest = detected / "poethepoet"
        else:
            dest = _prompt_for_skills_dir(detected) / "poethepoet"

    if dest.exists():
        existing = _read_skill_version(dest)
        cmp = _compare_versions(existing, __version__)

        if upgrade:
            if cmp >= 0:
                status = "up to date" if cmp == 0 else f"newer ({existing})"
                print(f"Installed skill is already {status} — skipping.")
                return
            print(f"Upgrading skill from {existing or 'unknown'} to {__version__}...")
        else:
            if existing:
                if cmp > 0:
                    print(
                        f"Installed skill version {existing} is newer "
                        f"than poe {__version__}."
                    )
                    if not _confirm("Downgrade? [y/N] ", default=False):
                        print("Cancelled.")
                        return
                elif cmp == 0:
                    print(f"Skill version {existing} is already up to date.")
                    if not _confirm("Reinstall? [y/N] ", default=False):
                        print("Cancelled.")
                        return
                else:
                    print(f"Upgrading skill from {existing} to {__version__}.")
                    if not _confirm("Proceed? [Y/n] ", default=True):
                        print("Cancelled.")
                        return
            else:
                print(f"Skill is already installed at {dest} (version unknown).")
                if not _confirm("Overwrite? [y/N] ", default=False):
                    print("Cancelled.")
                    return

        shutil.rmtree(dest)

    _copy_skill(dest)
    print(f"Skill installed to {dest}")


def _detect_skills_dir() -> Path | None:
    """Return the most likely skills directory based on installed agent tooling."""
    home = Path.home()

    project_candidates = [
        (Path(".claude"), Path(".claude").resolve() / "skills"),
        (Path(".codex"), Path(".codex").resolve() / "skills"),
        (Path(".pi"), Path(".pi").resolve() / "skills"),
    ]
    for marker, skills_dir in project_candidates:
        if marker.is_dir():
            return skills_dir

    user_candidates = [
        (home / ".claude", home / ".claude" / "skills"),
        (home / ".codex", home / ".codex" / "skills"),
        (home / ".pi" / "agent", home / ".pi" / "agent" / "skills"),
        (home / ".agents", home / ".agents" / "skills"),
    ]
    for marker, skills_dir in user_candidates:
        if marker.is_dir():
            return skills_dir

    return None


def _prompt_for_skills_dir(detected: Path | None) -> Path:
    """
    Prompt the user to confirm a detected directory or enter one manually.
    Raises SystemExit(0) if the user cancels.
    """
    if detected:
        answer = input(f"Install to {detected}? [Y/n] ").strip().lower()
        if answer in ("", "y", "yes"):
            return detected
        if answer not in ("n", "no") and answer.startswith(("/", "~", ".", "..")):
            return Path(answer).expanduser().resolve()

    path_str = input("Enter skills directory path: ").strip()
    if not path_str:
        print("No path provided. Installation cancelled.")
        raise SystemExit(0)
    return Path(path_str).expanduser().resolve()


def _read_skill_version(skill_dir: Path) -> str | None:
    """Read the version string from an installed skill's version.txt."""
    try:
        return (skill_dir / "version.txt").read_text().strip() or None
    except OSError:
        return None


def _compare_versions(v1: str | None, v2: str) -> int:
    """
    Compare two semver-style version strings (e.g. '0.45.0').
    Returns -1 if v1 < v2, 0 if equal, 1 if v1 > v2.
    None is treated as 0.0.0.
    """

    def parse(v: str) -> tuple[int, ...]:
        try:
            return tuple(int(x) for x in v.strip().split(".")[:3])
        except ValueError:
            return (0, 0, 0)

    t1 = parse(v1) if v1 else (0, 0, 0)
    t2 = parse(v2)
    return 0 if t1 == t2 else (-1 if t1 < t2 else 1)


def _confirm(prompt: str, default: bool) -> bool:
    """Prompt for yes/no. Returns default on empty input."""
    answer = input(prompt).strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def _copy_skill(dest: Path) -> None:
    """Copy the bundled skill tree to dest, creating parent directories as needed."""

    def _copy_traversable(src: Traversable, dst: Path) -> None:
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            for child in src.iterdir():
                _copy_traversable(child, dst / child.name)
        else:
            dst.write_bytes(src.read_bytes())

    _copy_traversable(files("poethepoet.skills") / "poethepoet", dest)
