"""
Fixtures for completion tests.
"""

import sys
from importlib import import_module
from pathlib import Path

import pytest


def _path_import(root: Path, target: str):
    module_path, separator, attr_name = target.partition(":")
    if not separator or not module_path or not attr_name:
        raise ValueError(f"Invalid import target: {target!r}")

    original_sys_path = list(sys.path)
    try:
        sys.path.insert(0, str(root))
        module = import_module(module_path)
        return getattr(module, attr_name)
    finally:
        sys.path[:] = original_sys_path


# Import from harness modules using path-based import
ZshHarnessResult = _path_import(Path(__file__).parent, "harness:ZshHarnessResult")
ZshHarnessConfig = _path_import(Path(__file__).parent, "harness:ZshHarnessConfig")
ZshHarnessRunner = _path_import(Path(__file__).parent, "harness:ZshHarnessRunner")

BashHarnessResult = _path_import(
    Path(__file__).parent, "bash_harness:BashHarnessResult"
)
BashHarnessConfig = _path_import(
    Path(__file__).parent, "bash_harness:BashHarnessConfig"
)
BashHarnessRunner = _path_import(
    Path(__file__).parent, "bash_harness:BashHarnessRunner"
)


@pytest.fixture
def zsh_harness(tmp_path):
    """
    Create a zsh harness that stubs completion builtins and captures their calls.

    Returns a function that runs a completion script with specified words and
    returns a ZshHarnessResult with captured information.
    """
    # Create runner once and reuse to maintain counter across calls
    runner = ZshHarnessRunner(tmp_path)
    runner.__enter__()

    def run(
        script: str,
        words: list[str],
        current: int,
        mock_poe_output: dict[str, str] | None = None,
        pre_cache: dict[str, list[str]] | None = None,
    ) -> ZshHarnessResult:
        """
        Run zsh completion script with stubbed builtins.

        Args:
            script: The zsh completion script to test
            words: The command line words (e.g., ["poe", "task", "--opt"])
            current: Index of current word being completed (1-based for zsh)
            mock_poe_output: Dict mapping command suffixes to output
                e.g., {"_zsh_describe_tasks": "task1:desc1\\ntask2:desc2"}
            pre_cache: Dict mapping cache IDs to pre-populated cache contents
                e.g., {"poe_tasks__path": ["task1:desc1", "task2:desc2"]}

        Returns:
            ZshHarnessResult with captured completion behavior
        """
        config = ZshHarnessConfig(
            words=words,
            current=current,
            mock_poe_output=mock_poe_output or {},
            pre_cache=pre_cache or {},
        )

        return runner.run(script, config)

    yield run

    runner.__exit__(None, None, None)


@pytest.fixture
def bash_harness(tmp_path):
    """
    Create a bash harness that stubs completion builtins and captures their calls.

    Returns a function that runs a completion script with specified words and
    returns a BashHarnessResult with captured information.
    """
    # Create runner once and reuse to maintain counter across calls
    runner = BashHarnessRunner(tmp_path)
    runner.__enter__()

    def run(
        script: str,
        words: list[str],
        current: int,
        mock_poe_output: dict[str, str] | None = None,
        mock_files: list[str] | None = None,
    ) -> BashHarnessResult:
        """
        Run bash completion script with stubbed builtins.

        Args:
            script: The bash completion script to test
            words: The command line words (e.g., ["poe", "task", "--opt"])
            current: Index of current word being completed (0-based for bash)
            mock_poe_output: Dict mapping command suffixes to output
                e.g., {"_list_tasks": "task1 task2"}
            mock_files: List of mock files for _filedir completion
                e.g., ["file1.txt", "file2.py"]

        Returns:
            BashHarnessResult with captured completion behavior
        """
        config = BashHarnessConfig(
            words=words,
            current=current,
            mock_poe_output=mock_poe_output or {},
            mock_files=mock_files or [],
        )

        return runner.run(script, config)

    yield run

    runner.__exit__(None, None, None)
