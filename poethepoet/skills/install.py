from __future__ import annotations

import re
import shutil
import sys
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING

from ..exceptions import PoeException

if TYPE_CHECKING:
    from collections.abc import Sequence
    from importlib.resources.abc import Traversable

SKILL_NAME = "poethepoet"

_VERSION_PATTERN = re.compile(
    r"^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?"
    r"(?:[.-]?(dev|a|alpha|b|beta|rc|c)\.?(\d*))?\s*$",
    re.IGNORECASE,
)
_PRE_RELEASE_RANK = {
    "dev": 0,
    "a": 1,
    "alpha": 1,
    "b": 2,
    "beta": 2,
    "c": 3,
    "rc": 3,
}
_FINAL_RELEASE_RANK = 4


def main(cli_args: Sequence[str]) -> None:
    """
    Entry point for the ``poe _install_skill`` builtin.

    CLI: poe _install_skill [<skills-dir>] [-u | --upgrade]
    """
    from argparse import ArgumentParser

    parser = ArgumentParser(
        prog="poe _install_skill",
        description=(
            "Install or upgrade the bundled poethepoet agent skill into "
            "<skills-dir>/poethepoet. Without <skills-dir> a directory is detected "
            "(.claude, .codex, .pi or .agents in the current directory, then in "
            "your home directory) and you are asked to confirm it."
        ),
    )
    parser.add_argument(
        "skills_dir",
        nargs="?",
        type=Path,
        help="Parent directory for skills, e.g. .claude/skills",
    )
    parser.add_argument(
        "-u",
        "--upgrade",
        action="store_true",
        help=(
            "Non-interactive: install, or replace an older installed version; "
            "skip if the installed version is the same or newer"
        ),
    )
    args = parser.parse_args(list(cli_args))

    try:
        install_skill(skills_dir=args.skills_dir, upgrade=args.upgrade)
    except PoeException as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from None


def install_skill(skills_dir: Path | None = None, upgrade: bool = False) -> None:
    """
    Install or upgrade the bundled agent skill to a skills directory.

    skills_dir: Parent directory for skills (skill installed at <dir>/poethepoet/).
                If None, auto-detects a suitable default and prompts to confirm.
    upgrade:    Non-interactive — overwrite if installed version is older;
                skip if equal or newer (never downgrades).
    """
    if skills_dir is not None:
        dest = skills_dir.expanduser().resolve() / SKILL_NAME
    else:
        detected = _detect_skills_dir()
        if upgrade:
            if detected is None:
                raise PoeException(
                    "Could not detect a skills directory. "
                    "Provide a path: poe _install_skill <skills-dir> --upgrade"
                )
            dest = detected / SKILL_NAME
        else:
            dest = _prompt_for_skills_dir(detected) / SKILL_NAME

    dest = _resolve_destination(dest)
    bundled_version = _bundled_version()

    if dest.exists():
        if not (dest / "SKILL.md").is_file():
            raise PoeException(
                f"{dest} exists but doesn't contain an installed skill, so it was "
                "left untouched. Remove it or choose another skills directory."
            )

        existing = _read_skill_version(dest)
        cmp = _compare_versions(existing, bundled_version)

        if upgrade:
            if cmp >= 0:
                status = "up to date" if cmp == 0 else f"newer ({existing})"
                print(f"Installed skill is already {status} — skipping.")
                return
            print(
                f"Upgrading skill from {existing or 'unknown'} to {bundled_version}..."
            )
        elif existing:
            if cmp > 0:
                print(
                    f"Installed skill version {existing} is newer "
                    f"than the bundled version {bundled_version}."
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
                print(f"Upgrading skill from {existing} to {bundled_version}.")
                if not _confirm("Proceed? [Y/n] ", default=True):
                    print("Cancelled.")
                    return
        else:
            print(f"Skill is already installed at {dest} (version unknown).")
            if not _confirm("Overwrite? [y/N] ", default=False):
                print("Cancelled.")
                return

    _install_copy(dest)
    print(f"Skill installed to {dest}")


def _resolve_destination(dest: Path) -> Path:
    """
    Validate the install destination, following a symlinked skill dir (as created
    by some skill managers) to the directory it points at.
    """
    if dest.is_symlink():
        target = dest.resolve()
        if not target.is_dir():
            raise PoeException(
                f"{dest} is a symlink to {target}, which is not a directory. "
                "Remove the link or choose another skills directory."
            )
        print(f"{dest} is a symlink, installing to its target {target}")
        dest = target
    elif dest.exists() and not dest.is_dir():
        raise PoeException(
            f"{dest} exists and is not a directory. "
            "Remove it or choose another skills directory."
        )

    if bundled_dir := _bundled_skill_path():
        bundled_dir = bundled_dir.resolve()
        if (
            dest == bundled_dir
            or bundled_dir in dest.parents
            or dest in bundled_dir.parents
        ):
            raise PoeException(
                f"Refusing to install the skill to {dest}, because it overlaps the "
                f"skill bundled with poe at {bundled_dir}."
            )
    return dest


def _detect_skills_dir() -> Path | None:
    """
    Return the most likely skills directory based on installed agent tooling.
    """
    home = Path.home()

    project_candidates = [Path(".claude"), Path(".codex"), Path(".pi"), Path(".agents")]
    for marker in project_candidates:
        if marker.is_dir():
            return marker.resolve() / "skills"

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
        answer = _input(f"Install to {detected}? [Y/n] ").strip()
        if answer.lower() in ("", "y", "yes"):
            return detected
        if answer.lower() not in ("n", "no"):
            return Path(answer).expanduser().resolve()

    path_str = _input("Enter skills directory path: ").strip()
    if not path_str:
        print("No path provided. Installation cancelled.")
        raise SystemExit(0)
    return Path(path_str).expanduser().resolve()


def _input(prompt: str) -> str:
    """
    Read a line of user input, failing cleanly when there is no interactive input.
    """
    try:
        return input(prompt)
    except EOFError:
        print()
        raise PoeException(
            "No input available to answer the prompt. To install non-interactively "
            "pass a skills directory and --upgrade, e.g. "
            "poe _install_skill .claude/skills --upgrade"
        ) from None
    except KeyboardInterrupt:
        print("\nCancelled.")
        raise SystemExit(130) from None


def _read_skill_version(skill_dir: Path) -> str | None:
    """
    Read the version string from an installed skill's version.txt.
    """
    try:
        return (skill_dir / "version.txt").read_text().strip() or None
    except OSError:
        return None


def _bundled_skill() -> Traversable:
    return files("poethepoet.skills") / SKILL_NAME


def _bundled_skill_path() -> Path | None:
    """
    Return the bundled skill's location on disk, if it is a regular directory.
    """
    bundled = _bundled_skill()
    return bundled if isinstance(bundled, Path) else None


def _bundled_version() -> str:
    return (_bundled_skill() / "version.txt").read_text().strip()


def _parse_version(version: str) -> tuple[int, ...] | None:
    """
    Parse a version like '0.45.0', '0.49.0rc1' or '0.49.0.dev2' into a sortable
    tuple, or return None if it isn't recognised.
    """
    if not (match := _VERSION_PATTERN.match(version)):
        return None
    major, minor, patch, pre_label, pre_number = match.groups()
    stage = _PRE_RELEASE_RANK[pre_label.lower()] if pre_label else _FINAL_RELEASE_RANK
    return (
        int(major),
        int(minor or 0),
        int(patch or 0),
        stage,
        int(pre_number or 0),
    )


def _compare_versions(v1: str | None, v2: str) -> int:
    """
    Compare two version strings (e.g. '0.45.0', '0.49.0rc1').
    Returns -1 if v1 < v2, 0 if equal, 1 if v1 > v2.
    A missing or unrecognised v1 is treated as older than any version.
    """
    parsed_v1 = _parse_version(v1) if v1 else None
    parsed_v2 = _parse_version(v2)
    if parsed_v1 is None:
        return -1 if parsed_v2 is not None else 0
    if parsed_v2 is None:
        return 1
    return 0 if parsed_v1 == parsed_v2 else (-1 if parsed_v1 < parsed_v2 else 1)


def _confirm(prompt: str, default: bool) -> bool:
    """
    Prompt for yes/no. Returns default on empty input.
    """
    answer = _input(prompt).strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def _install_copy(dest: Path) -> None:
    """
    Copy the bundled skill tree to dest, replacing any existing copy only once
    the new copy is complete.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.with_name(f".{dest.name}.installing")
    backup = dest.with_name(f".{dest.name}.previous")
    for leftover in (staging, backup):
        if leftover.exists():
            shutil.rmtree(leftover)

    try:
        _copy_traversable(_bundled_skill(), staging)
    except OSError as error:
        shutil.rmtree(staging, ignore_errors=True)
        raise PoeException(f"Failed to install the skill to {dest}: {error}") from None

    if dest.exists():
        dest.rename(backup)
    staging.rename(dest)
    shutil.rmtree(backup, ignore_errors=True)


def _copy_traversable(src: Traversable, dst: Path) -> None:
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            if child.name == "__pycache__":
                continue
            _copy_traversable(child, dst / child.name)
    else:
        dst.write_bytes(src.read_bytes())
