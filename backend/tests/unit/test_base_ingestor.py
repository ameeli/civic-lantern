from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from civic_lantern.jobs.base_ingestor import BaseIngestor


class FakeIngestor(BaseIngestor):
    """Concrete subclass for testing the BaseIngestor workflow."""

    entity_name = "fake"

    def __init__(self, client, session, *, fetch_return=None, transform_return=None):
        super().__init__(client, session)
        self._fetch_return = fetch_return or []
        self._transform_return = transform_return or []

    async def fetch(self, start_date: str, end_date: str, **kwargs: Any) -> list:
        return self._fetch_return

    def transform(self, raw_data: List[Dict[str, Any]]) -> list:
        return self._transform_return

    def create_service(self) -> AsyncMock:
        service = AsyncMock()
        service.upsert_batch.return_value = {
            "upserted": len(self._transform_return),
            "errors": 0,
            "failed_ids": [],
        }
        return service


@pytest.mark.unit
@pytest.mark.asyncio
class TestBaseIngestorWorkflow:
    """Test the template method workflow in BaseIngestor."""

    async def test_happy_path(self):
        """Fetch → transform → upsert returns stats."""
        ingestor = FakeIngestor(
            client=AsyncMock(),
            session=AsyncMock(),
            fetch_return=[{"id": "1"}],
            transform_return=["validated_obj"],
        )

        stats = await ingestor.run(start_date="2024-01-01", end_date="2024-06-01")

        assert stats["upserted"] == 1
        assert stats["errors"] == 0

    async def test_empty_transform_returns_none(self):
        """When transform returns empty list, return None without upserting."""
        ingestor = FakeIngestor(
            client=AsyncMock(),
            session=AsyncMock(),
            fetch_return=[{"id": "1"}],
            transform_return=[],
        )

        result = await ingestor.run(start_date="2024-01-01", end_date="2024-06-01")

        assert result is None

    async def test_default_date_range_uses_eastern(self, mocker):
        """When no dates provided, defaults to last 7 days in US/Eastern."""
        fec_tz = ZoneInfo("America/New_York")
        fake_now = datetime(2025, 6, 15, 10, 0, tzinfo=fec_tz)
        mock_dt = mocker.patch("civic_lantern.jobs.base_ingestor.datetime")
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        ingestor = FakeIngestor(
            client=AsyncMock(),
            session=AsyncMock(),
        )

        start, end = ingestor._resolve_dates(None, None)

        assert start == "2025-06-08"
        assert end == "2025-06-15"
        # Verify now() was called with US/Eastern timezone
        mock_dt.now.assert_called_once_with(fec_tz)

    async def test_provided_dates_pass_through(self):
        """Explicit dates are not overridden."""
        ingestor = FakeIngestor(
            client=AsyncMock(),
            session=AsyncMock(),
        )

        start, end = ingestor._resolve_dates("2024-03-01", "2024-09-01")

        assert start == "2024-03-01"
        assert end == "2024-09-01"

    async def test_upsert_error_propagates(self):
        """Exceptions from upsert_batch bubble up after logging."""
        ingestor = FakeIngestor(
            client=AsyncMock(),
            session=AsyncMock(),
            fetch_return=[{"id": "1"}],
            transform_return=["validated_obj"],
        )
        # Override create_service to return a failing service
        failing_service = AsyncMock()
        failing_service.upsert_batch.side_effect = Exception("DB gone")
        ingestor.create_service = lambda: failing_service

        with pytest.raises(Exception, match="DB gone"):
            await ingestor.run(start_date="2024-01-01", end_date="2024-06-01")
