from unittest.mock import AsyncMock

import pytest

from civic_lantern.db.models.ingestion_run import IngestionRun, IngestionRunStatus
from civic_lantern.services.data.ingestion_run import IngestionRunService
from tests.unit.conftest import scalars_first_result


@pytest.mark.unit
@pytest.mark.asyncio
class TestStartRun:
    async def test_creates_new_row_when_none_exists(self, mock_session: AsyncMock):
        mock_session.execute.return_value = scalars_first_result(None)
        service = IngestionRunService(mock_session)

        run = await service.start_run("candidates")

        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert added.ingestor_name == "candidates"
        assert added.cycle is None
        assert added.status == IngestionRunStatus.IN_PROGRESS
        mock_session.commit.assert_awaited_once()
        assert run is added

    async def test_reuses_existing_row_and_clears_prior_error(
        self, mock_session: AsyncMock
    ):
        existing = IngestionRun(
            ingestor_name="candidates",
            cycle=None,
            status=IngestionRunStatus.FAILED,
            error_message="previous failure",
        )
        mock_session.execute.return_value = scalars_first_result(existing)
        service = IngestionRunService(mock_session)

        run = await service.start_run("candidates")

        mock_session.add.assert_not_called()
        assert run is existing
        assert run.status == IngestionRunStatus.IN_PROGRESS
        assert run.error_message is None


@pytest.mark.unit
@pytest.mark.asyncio
class TestCompleteRun:
    async def test_success_sets_watermark_and_clears_error(
        self, mock_session: AsyncMock
    ):
        run = IngestionRun(
            ingestor_name="candidates", status=IngestionRunStatus.IN_PROGRESS
        )
        service = IngestionRunService(mock_session)

        await service.complete_run(run, success=True)

        assert run.status == IngestionRunStatus.SUCCESS
        assert run.error_message is None
        assert run.last_run_completed_at is not None
        mock_session.commit.assert_awaited_once()

    async def test_failure_records_error_and_leaves_watermark_untouched(
        self, mock_session: AsyncMock
    ):
        run = IngestionRun(
            ingestor_name="candidates",
            status=IngestionRunStatus.IN_PROGRESS,
            last_run_completed_at=None,
        )
        service = IngestionRunService(mock_session)

        await service.complete_run(run, success=False, error_message="FEC API down")

        assert run.status == IngestionRunStatus.FAILED
        assert run.error_message == "FEC API down"
        assert run.last_run_completed_at is None


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetWatermark:
    async def test_returns_none_when_no_row(self, mock_session: AsyncMock):
        mock_session.execute.return_value = scalars_first_result(None)
        service = IngestionRunService(mock_session)

        assert await service.get_watermark("candidates") is None

    async def test_returns_last_run_completed_at(self, mock_session: AsyncMock):
        run = IngestionRun(
            ingestor_name="candidates",
            last_run_completed_at="2026-01-01T00:00:00+00:00",
        )
        mock_session.execute.return_value = scalars_first_result(run)
        service = IngestionRunService(mock_session)

        assert await service.get_watermark("candidates") == "2026-01-01T00:00:00+00:00"
