from pathlib import Path
import pytest
import toml


PROJECT_ROOT = Path(__file__).joinpath("../..").resolve()


@pytest.fixture
def pyproject():
    with open(PROJECT_ROOT.joinpath("pyproject.toml"), "r") as toml_file:
        return toml.load(toml_file)
