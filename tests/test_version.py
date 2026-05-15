from pathlib import Path

from poethepoet import __version__


def test_version(pyproject):
    assert (
        __version__ == pyproject["project"]["version"]
    ), "Project version should match in package and package config"

    version_txt = Path(__file__).parents[1] / "poethepoet/skills/poethepoet/version.txt"
    assert (
        __version__ == version_txt.read_text().strip()
    ), "Project version should match in skills/poethepoet/version.txt"
