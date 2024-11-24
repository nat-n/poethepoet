import os
from pathlib import Path
from shutil import rmtree

import pytest

from poethepoet.scripts import rm

_test_file_tree = {
    "pkg": {
        "__pycache__": {"foo.pyc": "XXX"},
        "foo.py": "XXX",
        "bar": {
            "baz.py": "XXX",
            "__pycache__": {"baz.pyc": "XXX"},
        },
    },
    ".mypy_cache": "XXX",
    ".pytest_cache": "XXX",
    "readme.md": "XXX",
    "garbage.md": "XXX",
    "__pycache__": {},
}


@pytest.fixture
def test_file_tree_dir(poe_project_path):
    path = poe_project_path / "tests" / "temp" / "rm_test"
    path.mkdir(parents=True, exist_ok=True)
    yield path
    rmtree(path)


@pytest.fixture
def test_file_tree_nodes(test_file_tree_dir):
    def _iter_dir(work_dir: Path, items: dict):
        for node_name, content in items.items():
            node_path = work_dir / node_name
            if isinstance(content, dict):
                yield (node_path, None)
                yield from _iter_dir(node_path, content)
            else:
                yield (node_path, "content")

    return tuple(_iter_dir(test_file_tree_dir, _test_file_tree))


@pytest.fixture
def test_dir_structure(test_file_tree_dir, test_file_tree_nodes):
    """
    Stage a temporary directory structure full of files so we can delete some of them
    """

    for path, content in test_file_tree_nodes:
        if content:
            path.write_text(content)
        else:
            path.mkdir(parents=True, exist_ok=True)

    cwd = Path.cwd()
    os.chdir(test_file_tree_dir)

    try:
        yield test_file_tree_dir
    finally:
        os.chdir(cwd)


def test_rm_dry_mode(test_dir_structure, capsys, test_file_tree_nodes):
    rm(".mypy_cache", ".pytest_cache", "./**/__pycache__", verbosity=0, dry_run=True)

    captured = capsys.readouterr()
    assert captured.out == ("Deleting paths matching './**/__pycache__'\n")
    assert captured.err == ""

    for path, content in test_file_tree_nodes:
        assert path.exists()


def test_rm_deletion(test_dir_structure, capsys, test_file_tree_nodes):
    rm(".mypy_cache", ".pytest_cache", "./**/__pycache__")

    captured = capsys.readouterr()
    assert captured.out == ("Deleting paths matching './**/__pycache__'\n")
    assert captured.err == ""

    for path, content in test_file_tree_nodes:
        if any(
            name in str(path)
            for name in ("__pycache__", ".mypy_cache", ".pytest_cache")
        ):
            assert not path.exists()
        else:
            assert path.exists()


def test_rm_dry_mode_quiet(test_dir_structure, capsys, test_file_tree_nodes):
    rm(".mypy_cache", ".pytest_cache", "./**/__pycache__", verbosity=-1, dry_run=True)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    for path, content in test_file_tree_nodes:
        assert path.exists()


def test_rm_dry_mode_verbose(
    test_dir_structure, capsys, test_file_tree_nodes, is_windows
):
    rm(".mypy_cache", ".pytest_cache", "./**/__pycache__", verbosity=1, dry_run=True)

    captured = capsys.readouterr()
    if is_windows:
        assert captured.out == (
            "Deleting file '.mypy_cache'\n"
            "Deleting file '.pytest_cache'\n"
            "Deleting paths matching './**/__pycache__'\n"
            "Deleting directory '__pycache__'\n"
            "Deleting directory 'pkg\\__pycache__'\n"
            "Deleting directory 'pkg\\bar\\__pycache__'\n"
        )
    else:
        assert captured.out == (
            "Deleting file '.mypy_cache'\n"
            "Deleting file '.pytest_cache'\n"
            "Deleting paths matching './**/__pycache__'\n"
            "Deleting directory '__pycache__'\n"
            "Deleting directory 'pkg/__pycache__'\n"
            "Deleting directory 'pkg/bar/__pycache__'\n"
        )
    assert captured.err == ""

    for path, content in test_file_tree_nodes:
        assert path.exists()


def test_rm_no_patterns_verbose(test_dir_structure, capsys, test_file_tree_nodes):
    rm(verbosity=1, dry_run=True)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    for path, content in test_file_tree_nodes:
        assert path.exists()


def test_rm_innert_patterns(test_dir_structure, capsys, test_file_tree_nodes):
    rm("nee", "shrubbery", dry_run=True)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    for path, content in test_file_tree_nodes:
        assert path.exists()


def test_rm_innert_patterns_verbose(test_dir_structure, capsys, test_file_tree_nodes):
    rm("nee", "shrubbery", verbosity=1, dry_run=True)

    captured = capsys.readouterr()
    assert captured.out == (
        "No files or directories to delete matching 'nee'\n"
        "No files or directories to delete matching 'shrubbery'\n"
    )
    assert captured.err == ""

    for path, content in test_file_tree_nodes:
        assert path.exists()
