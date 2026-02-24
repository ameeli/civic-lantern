from unittest.mock import AsyncMock

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
