from unittest.mock import AsyncMock, MagicMock

import pytest

from civic_lantern.jobs.manager import IngestionManager


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def manager(mock_client: AsyncMock) -> IngestionManager:
    m = IngestionManager()
    m._client = mock_client
    return m


# ---------------------------------------------------------------------------
# DB result mock helpers — usable in any unit test
# ---------------------------------------------------------------------------


def scalar_result(value):
    """Mock a DB result where .scalar() → value."""
    m = MagicMock()
    m.scalar.return_value = value
    return m


def scalars_all_result(items):
    """Mock a DB result where .scalars().all() → items."""
    m = MagicMock()
    m.scalars.return_value.all.return_value = items
    return m


def scalars_first_result(item):
    """Mock a DB result where .scalars().first() → item."""
    m = MagicMock()
    m.scalars.return_value.first.return_value = item
    return m


def mappings_result(items):
    """Mock a DB result where .mappings().all() → items and .mappings().first() → items[0]."""
    mappings = MagicMock()
    mappings.all.return_value = items
    mappings.first.return_value = items[0] if items else None
    result = MagicMock()
    result.mappings.return_value = mappings
    return result
