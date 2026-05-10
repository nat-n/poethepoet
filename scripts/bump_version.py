import re
import sys
from pathlib import Path

_BUMP_TYPES = ("minor", "tiny")


def main(version: str | None = None) -> None:
    """
    Bump the package version in all source files that embed it.
    """
    if not version:
        sys.exit("Specify a bump type (minor/tiny) or an explicit version (e.g. 1.2.3)")

    root = Path(__file__).parent.parent
    ver_file = root / "poethepoet" / "__version__.py"

    match = re.search(r'__version__ = "(.+)"', ver_file.read_text())
    if not match:
        sys.exit(f"Could not find __version__ in {ver_file}")
    current = match.group(1)
    parts = current.split(".")

    if version == "minor":
        new_version = f"{parts[0]}.{int(parts[1]) + 1}.0"
    elif version == "tiny":
        new_version = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"
    elif re.fullmatch(r"\d+\.\d+\.\d+(a|b|rc)\d+|\d+\.\d+\.\d+", version):
        new_version = version
    else:
        sys.exit(
            f"Invalid argument {version!r}: "
            "expected 'minor', 'tiny', or X.Y.Z[{'{a|b|rc}N'}]"
        )

    print(f"Bumping version: {current} → {new_version}")

    _update_file(
        root / "pyproject.toml",
        root,
        lambda c: re.sub(
            r'^(version\s*=\s*")[^"]+(")',
            rf"\g<1>{new_version}\2",
            c,
            count=1,
            flags=re.MULTILINE,
        ),
    )
    _update_file(
        root / "poethepoet" / "__version__.py",
        root,
        lambda c: re.sub(
            r'^(__version__\s*=\s*")[^"]+(")',
            rf"\g<1>{new_version}\2",
            c,
            count=1,
            flags=re.MULTILINE,
        ),
    )
    _update_file(
        root / "poethepoet" / "skills" / "poethepoet" / "version.txt",
        root,
        lambda _: new_version + "\n",
    )
    _update_file(
        root / "poethepoet" / "skills" / "poethepoet" / "SKILL.md",
        root,
        lambda c: c.replace(current, new_version),
    )


def _update_file(path: Path, root: Path, transform) -> None:
    content = path.read_text()
    new_content = transform(content)
    rel = path.relative_to(root)
    if new_content == content:
        print(f"  WARNING: no change in {rel}")
        return
    path.write_text(new_content)
    print(f"  Updated {rel}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Bump the package version across all source files."
    )
    parser.add_argument(
        "version",
        help=(
            "Version component to bump (minor, tiny) "
            "or an explicit version (e.g. 1.2.3rc1)"
        ),
    )
    args = parser.parse_args()
    main(args.version)
