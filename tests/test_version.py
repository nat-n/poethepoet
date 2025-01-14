from poethepoet import __version__


def test_version(pyproject):
    assert (
        __version__ == pyproject["project"]["version"]
    ), "Project version should match in package and package config"
