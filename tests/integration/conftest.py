"""Fixtures and collection rules for integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

INTEGRATION_DIR = Path(__file__).parent


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Mark every test collected under tests/integration/ as an integration test."""
    for item in items:
        if INTEGRATION_DIR in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.integration)
