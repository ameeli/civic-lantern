"""Integration tests for IngestionRunService and the ingestion_runs table."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.enums import SupportOpposeEnum
from civic_lantern.db.models.ingestion_run import IngestionRun, IngestionRunStatus
from civic_lantern.db.models.inside_totals_by_candidate import InsideTotalsByCandidate
from civic_lantern.db.models.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidate,
)
from civic_lantern.services.data.ingestion_run import IngestionRunService


@pytest.mark.integration
@pytest.mark.asyncio
class TestIngestionRunUniqueConstraints:
    async def test_rejects_duplicate_name_and_cycle(self, async_db: AsyncSession):
        async_db.add(
            IngestionRun(
                ingestor_name="inside_totals_by_candidate",
                cycle=2024,
                status=IngestionRunStatus.SUCCESS,
                started_at=datetime.now(timezone.utc),
            )
        )
        await async_db.commit()

        async_db.add(
            IngestionRun(
                ingestor_name="inside_totals_by_candidate",
                cycle=2024,
                status=IngestionRunStatus.IN_PROGRESS,
                started_at=datetime.now(timezone.utc),
            )
        )
        with pytest.raises(IntegrityError):
            await async_db.commit()
        await async_db.rollback()

    async def test_rejects_duplicate_name_with_null_cycle(self, async_db: AsyncSession):
        async_db.add(
            IngestionRun(
                ingestor_name="candidates",
                cycle=None,
                status=IngestionRunStatus.SUCCESS,
                started_at=datetime.now(timezone.utc),
            )
        )
        await async_db.commit()

        async_db.add(
            IngestionRun(
                ingestor_name="candidates",
                cycle=None,
                status=IngestionRunStatus.IN_PROGRESS,
                started_at=datetime.now(timezone.utc),
            )
        )
        with pytest.raises(IntegrityError):
            await async_db.commit()
        await async_db.rollback()

    async def test_allows_same_name_different_cycles(self, async_db: AsyncSession):
        async_db.add(
            IngestionRun(
                ingestor_name="inside_totals_by_candidate",
                cycle=2024,
                status=IngestionRunStatus.SUCCESS,
                started_at=datetime.now(timezone.utc),
            )
        )
        async_db.add(
            IngestionRun(
                ingestor_name="inside_totals_by_candidate",
                cycle=2026,
                status=IngestionRunStatus.SUCCESS,
                started_at=datetime.now(timezone.utc),
            )
        )
        await async_db.commit()  # should not raise


@pytest.mark.integration
@pytest.mark.asyncio
class TestIngestionRunServiceWatermark:
    async def test_start_run_creates_row(self, async_db: AsyncSession):
        service = IngestionRunService(async_db)
        run = await service.start_run("candidates")

        assert run.id is not None
        assert run.cycle is None
        assert run.status == IngestionRunStatus.IN_PROGRESS

    async def test_start_run_reuses_existing_row(self, async_db: AsyncSession):
        service = IngestionRunService(async_db)
        first = await service.start_run("candidates")
        await service.complete_run(first, success=True)

        second = await service.start_run("candidates")

        assert second.id == first.id
        assert second.status == IngestionRunStatus.IN_PROGRESS

    async def test_get_watermark_none_before_first_success(
        self, async_db: AsyncSession
    ):
        service = IngestionRunService(async_db)
        assert await service.get_watermark("candidates") is None

    async def test_get_watermark_after_success(self, async_db: AsyncSession):
        service = IngestionRunService(async_db)
        run = await service.start_run("candidates")
        await service.complete_run(run, success=True)

        watermark = await service.get_watermark("candidates")

        assert watermark is not None

    async def test_failed_run_does_not_set_watermark(self, async_db: AsyncSession):
        service = IngestionRunService(async_db)
        run = await service.start_run("candidates")
        await service.complete_run(run, success=False, error_message="boom")

        assert await service.get_watermark("candidates") is None
        assert run.status == IngestionRunStatus.FAILED
        assert run.error_message == "boom"

    async def test_failed_run_preserves_prior_watermark(self, async_db: AsyncSession):
        service = IngestionRunService(async_db)
        run = await service.start_run("candidates")
        await service.complete_run(run, success=True)
        first_watermark = await service.get_watermark("candidates")

        run = await service.start_run("candidates")
        await service.complete_run(run, success=False, error_message="boom again")

        assert await service.get_watermark("candidates") == first_watermark


@pytest.mark.integration
@pytest.mark.asyncio
class TestIngestionRunServiceOverlapGuard:
    async def test_has_active_run_false_when_none_in_progress(
        self, async_db: AsyncSession
    ):
        service = IngestionRunService(async_db)
        assert await service.has_active_run(timeout_minutes=180) is False

    async def test_has_active_run_true_for_recent_in_progress(
        self, async_db: AsyncSession
    ):
        service = IngestionRunService(async_db)
        await service.start_run("candidates")

        assert await service.has_active_run(timeout_minutes=180) is True

    async def test_has_active_run_false_for_stale_in_progress(
        self, async_db: AsyncSession
    ):
        async_db.add(
            IngestionRun(
                ingestor_name="candidates",
                cycle=None,
                status=IngestionRunStatus.IN_PROGRESS,
                started_at=datetime.now(timezone.utc) - timedelta(hours=5),
            )
        )
        await async_db.commit()

        service = IngestionRunService(async_db)
        assert await service.has_active_run(timeout_minutes=180) is False

    async def test_reset_stale_runs_marks_them_failed(self, async_db: AsyncSession):
        async_db.add(
            IngestionRun(
                ingestor_name="candidates",
                cycle=None,
                status=IngestionRunStatus.IN_PROGRESS,
                started_at=datetime.now(timezone.utc) - timedelta(hours=5),
            )
        )
        await async_db.commit()

        service = IngestionRunService(async_db)
        await service.reset_stale_runs(timeout_minutes=180)

        run = await service._find("candidates", cycle=None)
        assert run.status == IngestionRunStatus.FAILED

    async def test_reset_stale_runs_leaves_recent_runs_alone(
        self, async_db: AsyncSession
    ):
        service = IngestionRunService(async_db)
        run = await service.start_run("candidates")

        await service.reset_stale_runs(timeout_minutes=180)

        refreshed = await service._find("candidates", cycle=None)
        assert refreshed.status == IngestionRunStatus.IN_PROGRESS
        assert refreshed.id == run.id


@pytest.mark.integration
@pytest.mark.asyncio
class TestIngestionRunServiceReadyCycles:
    REQUIRED = ["inside_totals_by_candidate", "schedule_e_totals_by_candidate"]

    async def _succeed(self, service, ingestor_name, cycle):
        run = await service.start_run(ingestor_name, cycle)
        await service.complete_run(run, success=True)

    async def _seed_spending_data(self, async_db: AsyncSession, cycle: int) -> None:
        candidate = Candidate(candidate_id=f"C{cycle}", name="Test Candidate")
        async_db.add(candidate)
        await async_db.flush()
        async_db.add(
            InsideTotalsByCandidate(
                candidate_id=candidate.candidate_id,
                cycle=cycle,
                receipts=Decimal("100.00"),
                disbursements=Decimal("50.00"),
            )
        )
        async_db.add(
            ScheduleETotalsByCandidate(
                candidate_id=candidate.candidate_id,
                cycle=cycle,
                support_oppose_indicator=SupportOpposeEnum.SUPPORT,
                total=Decimal("25.00"),
            )
        )
        await async_db.commit()

    async def test_cycle_ready_when_both_ingestors_succeed_and_have_data(
        self, async_db: AsyncSession
    ):
        service = IngestionRunService(async_db)
        await self._succeed(service, "inside_totals_by_candidate", 2024)
        await self._succeed(service, "schedule_e_totals_by_candidate", 2024)
        await self._seed_spending_data(async_db, 2024)

        assert await service.get_ready_cycles(self.REQUIRED) == [2024]

    async def test_cycle_not_ready_when_only_one_ingestor_succeeds(
        self, async_db: AsyncSession
    ):
        service = IngestionRunService(async_db)
        await self._succeed(service, "inside_totals_by_candidate", 2024)

        assert await service.get_ready_cycles(self.REQUIRED) == []

    async def test_cycle_not_ready_when_succeeded_but_no_data(
        self, async_db: AsyncSession
    ):
        """A brand-new cycle whose first run 'succeeds' with zero FEC
        records must not be reported as ready."""
        service = IngestionRunService(async_db)
        await self._succeed(service, "inside_totals_by_candidate", 2024)
        await self._succeed(service, "schedule_e_totals_by_candidate", 2024)

        assert await service.get_ready_cycles(self.REQUIRED) == []

    async def test_cycle_stays_ready_after_later_transient_failure(
        self, async_db: AsyncSession
    ):
        """A transient failure re-ingesting an already-ready cycle (nightly
        re-runs every active cycle, not just new ones) must not un-ready it —
        the previously-ingested data is untouched."""
        service = IngestionRunService(async_db)
        await self._succeed(service, "inside_totals_by_candidate", 2024)
        await self._succeed(service, "schedule_e_totals_by_candidate", 2024)
        await self._seed_spending_data(async_db, 2024)
        assert await service.get_ready_cycles(self.REQUIRED) == [2024]

        run = await service.start_run("schedule_e_totals_by_candidate", 2024)
        await service.complete_run(run, success=False, error_message="transient 5xx")

        assert await service.get_ready_cycles(self.REQUIRED) == [2024]

    async def test_ready_cycles_ordered_newest_first(self, async_db: AsyncSession):
        service = IngestionRunService(async_db)
        for cycle in (2024, 2026):
            await self._succeed(service, "inside_totals_by_candidate", cycle)
            await self._succeed(service, "schedule_e_totals_by_candidate", cycle)
            await self._seed_spending_data(async_db, cycle)

        assert await service.get_ready_cycles(self.REQUIRED) == [2026, 2024]
