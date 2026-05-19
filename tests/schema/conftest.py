"""
Auto-applies `pytest.mark.schema` to the parity-test files in this
directory. Other tests under tests/schema/ (unit tests for the
translator, context, and __schema_fragment__ hook) are NOT auto-marked,
so they continue to run under the default `poe test` invocation.
"""

import pytest

# Filenames containing parity tests (slow, require the full schema build).
# Phase 3 will configure `poe test-quick` to exclude the `schema` marker.
_PARITY_TEST_FILES = frozenset(
    {
        "test_meta.py",
        "test_fixture_configs.py",
        "test_invalid_corpus.py",
        "test_mutation.py",
    }
)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """
    Apply the `schema` marker to parity-test items based on filename.
    """
    for item in items:
        if item.fspath.basename in _PARITY_TEST_FILES:
            item.add_marker(pytest.mark.schema)
