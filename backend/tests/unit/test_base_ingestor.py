from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch
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
            "inserted": len(self._transform_return),
            "updated": 0,
            "errors": 0,
            "failed_ids": [],
        }
        return service


class CycleScopedFakeIngestor(BaseIngestor):
    """Mirrors the real cycle-scoped ingestors: fetch() takes cycle, not dates."""

    entity_name = "fake_cycle_scoped"

    def __init__(self, client, session):
        super().__init__(client, session)
        self.captured_kwargs: Dict[str, Any] = {}

    async def fetch(self, cycle: int, **kwargs: Any) -> list:
        self.captured_kwargs = kwargs
        return []

    def transform(self, raw_data: List[Dict[str, Any]]) -> list:
        return []

    def create_service(self) -> AsyncMock:
        return AsyncMock()


@pytest.mark.unit
@pytest.mark.asyncio
class TestBaseIngestorWorkflow:
    """Test the template method workflow in BaseIngestor."""

    @patch("civic_lantern.jobs.base_ingestor.IngestionRunService", autospec=True)
    async def test_happy_path(self, MockRunService, mock_client, mock_session):
        """Fetch → transform → upsert returns stats."""
        MockRunService.return_value.start_run = AsyncMock(return_value=object())
        MockRunService.return_value.complete_run = AsyncMock()

        ingestor = FakeIngestor(
            client=mock_client,
            session=mock_session,
            fetch_return=[{"id": "1"}],
            transform_return=["validated_obj"],
        )

        stats = await ingestor.run(start_date="2024-01-01", end_date="2024-06-01")

        assert stats["inserted"] == 1
        assert stats["errors"] == 0

    @patch("civic_lantern.jobs.base_ingestor.IngestionRunService", autospec=True)
    async def test_empty_transform_returns_none(
        self, MockRunService, mock_client, mock_session
    ):
        """When transform returns empty list, return None without upserting."""
        MockRunService.return_value.start_run = AsyncMock(return_value=object())
        MockRunService.return_value.complete_run = AsyncMock()

        ingestor = FakeIngestor(
            client=mock_client,
            session=mock_session,
            fetch_return=[{"id": "1"}],
            transform_return=[],
        )

        result = await ingestor.run(start_date="2024-01-01", end_date="2024-06-01")

        assert result is None

    @patch("civic_lantern.jobs.base_ingestor.IngestionRunService", autospec=True)
    async def test_no_watermark_returns_none_start_for_full_pull(
        self, MockRunService, mocker, mock_client, mock_session
    ):
        """With no prior run, start_date is None — a full historical pull.

        A 1-day lookback would leave a newly-activated cycle's candidate
        roster incomplete, causing FK violations when spending totals for
        candidates outside that narrow window are ingested.
        """
        MockRunService.return_value.get_watermark = AsyncMock(return_value=None)

        fec_tz = ZoneInfo("America/New_York")
        fake_now = datetime(2025, 6, 15, 10, 0, tzinfo=fec_tz)
        mock_dt = mocker.patch("civic_lantern.jobs.base_ingestor.datetime")
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        ingestor = FakeIngestor(
            client=mock_client,
            session=mock_session,
        )

        start, end = await ingestor._resolve_dates(None, None)

        assert start is None
        assert end == "2025-06-15"
        mock_dt.now.assert_called_once_with(fec_tz)

    @patch("civic_lantern.jobs.base_ingestor.IngestionRunService", autospec=True)
    async def test_resolve_dates_uses_watermark_when_present(
        self, MockRunService, mocker, mock_client, mock_session
    ):
        """When a prior successful run exists, resumes from its watermark."""
        fec_tz = ZoneInfo("America/New_York")
        watermark = datetime(2025, 6, 10, 8, 0, tzinfo=fec_tz)
        MockRunService.return_value.get_watermark = AsyncMock(return_value=watermark)

        fake_now = datetime(2025, 6, 15, 10, 0, tzinfo=fec_tz)
        mock_dt = mocker.patch("civic_lantern.jobs.base_ingestor.datetime")
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        ingestor = FakeIngestor(client=mock_client, session=mock_session)

        start, end = await ingestor._resolve_dates(None, None)

        assert start == "2025-06-10"
        assert end == "2025-06-15"
        MockRunService.return_value.get_watermark.assert_awaited_once_with("fake")

    async def test_provided_dates_pass_through(self, mock_client, mock_session):
        """Explicit dates are not overridden, and no watermark lookup happens."""
        ingestor = FakeIngestor(
            client=mock_client,
            session=mock_session,
        )

        start, end = await ingestor._resolve_dates("2024-03-01", "2024-09-01")

        assert start == "2024-03-01"
        assert end == "2024-09-01"

    @patch("civic_lantern.jobs.base_ingestor.IngestionRunService", autospec=True)
    async def test_upsert_error_propagates(
        self, MockRunService, mock_client, mock_session
    ):
        """Exceptions from upsert_batch bubble up after logging."""
        MockRunService.return_value.start_run = AsyncMock(return_value=object())
        MockRunService.return_value.complete_run = AsyncMock()

        ingestor = FakeIngestor(
            client=mock_client,
            session=mock_session,
            fetch_return=[{"id": "1"}],
            transform_return=["validated_obj"],
        )
        # Override create_service to return a failing service
        failing_service = AsyncMock()
        failing_service.upsert_batch.side_effect = Exception("DB gone")
        ingestor.create_service = lambda: failing_service

        with pytest.raises(Exception, match="DB gone"):
            await ingestor.run(start_date="2024-01-01", end_date="2024-06-01")

    @patch("civic_lantern.jobs.base_ingestor.IngestionRunService", autospec=True)
    async def test_failure_rolls_back_before_recording(
        self, MockRunService, mock_client, mock_session
    ):
        """Session is rolled back before complete_run(success=False).

        Otherwise, if the failing exception left the session's transaction
        aborted, complete_run's own commit() would raise too — masking the
        original error and leaving the row stuck IN_PROGRESS.
        """
        MockRunService.return_value.start_run = AsyncMock(return_value=object())
        MockRunService.return_value.complete_run = AsyncMock()

        ingestor = FakeIngestor(
            client=mock_client,
            session=mock_session,
            fetch_return=[{"id": "1"}],
            transform_return=["validated_obj"],
        )
        failing_service = AsyncMock()
        failing_service.upsert_batch.side_effect = Exception("DB gone")
        ingestor.create_service = lambda: failing_service

        with pytest.raises(Exception, match="DB gone"):
            await ingestor.run(start_date="2024-01-01", end_date="2024-06-01")

        mock_session.rollback.assert_awaited_once()
        # rollback must happen before complete_run is called, not after
        assert mock_session.rollback.call_args is not None

    @patch("civic_lantern.jobs.base_ingestor.IngestionRunService", autospec=True)
    async def test_run_records_start_and_success(
        self, MockRunService, mock_client, mock_session
    ):
        """run() starts a tracked run keyed by (entity_name, cycle) and completes it."""
        run_row = object()
        mock_tracker = MockRunService.return_value
        mock_tracker.start_run = AsyncMock(return_value=run_row)
        mock_tracker.complete_run = AsyncMock()

        ingestor = CycleScopedFakeIngestor(client=mock_client, session=mock_session)

        await ingestor.run(cycle=2024)

        mock_tracker.start_run.assert_awaited_once_with("fake_cycle_scoped", 2024)
        mock_tracker.complete_run.assert_awaited_once_with(run_row, success=True)

    @patch("civic_lantern.jobs.base_ingestor.IngestionRunService", autospec=True)
    async def test_run_records_failure_with_error_message(
        self, MockRunService, mock_client, mock_session
    ):
        """A failed run is recorded with its error message, then re-raised."""
        run_row = object()
        mock_tracker = MockRunService.return_value
        mock_tracker.start_run = AsyncMock(return_value=run_row)
        mock_tracker.complete_run = AsyncMock()

        ingestor = FakeIngestor(
            client=mock_client,
            session=mock_session,
            fetch_return=[{"id": "1"}],
            transform_return=["validated_obj"],
        )
        failing_service = AsyncMock()
        failing_service.upsert_batch.side_effect = Exception("DB gone")
        ingestor.create_service = lambda: failing_service

        with pytest.raises(Exception, match="DB gone"):
            await ingestor.run(start_date="2024-01-01", end_date="2024-06-01")

        mock_tracker.complete_run.assert_awaited_once_with(
            run_row, success=False, error_message="DB gone"
        )

    @patch("civic_lantern.jobs.base_ingestor.IngestionRunService", autospec=True)
    async def test_run_records_success_even_with_empty_transform(
        self, MockRunService, mock_client, mock_session
    ):
        """An empty-but-valid run (e.g. no new records) still counts as success."""
        run_row = object()
        mock_tracker = MockRunService.return_value
        mock_tracker.start_run = AsyncMock(return_value=run_row)
        mock_tracker.complete_run = AsyncMock()

        ingestor = FakeIngestor(
            client=mock_client,
            session=mock_session,
            fetch_return=[{"id": "1"}],
            transform_return=[],
        )

        result = await ingestor.run(start_date="2024-01-01", end_date="2024-06-01")

        assert result is None
        mock_tracker.complete_run.assert_awaited_once_with(run_row, success=True)

    @patch("civic_lantern.jobs.base_ingestor.IngestionRunService", autospec=True)
    async def test_run_strips_date_kwargs_for_cycle_scoped_ingestors(
        self, MockRunService, mock_client, mock_session
    ):
        """run() strips start_date/end_date before calling fetch() when a
        cycle is present — cycle-scoped ingestors take no date window, but
        run_nightly() invokes them through the same ingest_batch() path used
        by date-windowed ingestors, which always forwards those kwargs
        (usually None). Centralized here so individual cycle-scoped
        ingestors don't each need to repeat the stripping.
        """
        MockRunService.return_value.start_run = AsyncMock(return_value=object())
        MockRunService.return_value.complete_run = AsyncMock()

        ingestor = CycleScopedFakeIngestor(client=mock_client, session=mock_session)

        await ingestor.run(cycle=2024, start_date=None, end_date="2026-01-01")

        assert "start_date" not in ingestor.captured_kwargs
        assert "end_date" not in ingestor.captured_kwargs
