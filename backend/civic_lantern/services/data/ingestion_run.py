import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import distinct, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.ingestion_run import IngestionRun, IngestionRunStatus
from civic_lantern.db.models.inside_totals_by_candidate import InsideTotalsByCandidate
from civic_lantern.db.models.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidate,
)
from civic_lantern.services.data.base import BaseService

logger = logging.getLogger(__name__)


class IngestionRunService(BaseService[IngestionRun]):
    """Tracks per-(ingestor_name, cycle) ingestion state.

    Backs three concerns: resuming date-windowed ingestors from a watermark,
    recording which cycles have complete spending data (readiness), and
    guarding against overlapping runs.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(model=IngestionRun, db=db)

    async def _find(
        self, ingestor_name: str, cycle: Optional[int]
    ) -> Optional[IngestionRun]:
        stmt = select(IngestionRun).where(
            IngestionRun.ingestor_name == ingestor_name,
            IngestionRun.cycle == cycle,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def start_run(
        self, ingestor_name: str, cycle: Optional[int] = None
    ) -> IngestionRun:
        """Record the start of a run, upserting the (ingestor_name, cycle) row."""
        run = await self._find(ingestor_name, cycle)
        now = datetime.now(timezone.utc)

        if run is None:
            run = IngestionRun(
                ingestor_name=ingestor_name,
                cycle=cycle,
                status=IngestionRunStatus.IN_PROGRESS,
                started_at=now,
            )
            self.db.add(run)
        else:
            run.status = IngestionRunStatus.IN_PROGRESS
            run.started_at = now
            run.error_message = None

        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def complete_run(
        self,
        run: IngestionRun,
        *,
        status: IngestionRunStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Mark a run as finished, recording its outcome.

        Only a clean SUCCESS advances `last_run_completed_at` — the
        watermark date-windowed ingestors resume from, and the readiness
        signal cycle-scoped ingestors publish to the frontend. PARTIAL_SUCCESS
        deliberately leaves it untouched so the next run re-covers whatever
        was missed instead of silently skipping past it.
        """
        run.status = status
        run.error_message = (
            None if status == IngestionRunStatus.SUCCESS else error_message
        )
        if status == IngestionRunStatus.SUCCESS:
            run.last_run_completed_at = datetime.now(timezone.utc)
        await self.db.commit()

    async def get_watermark(self, ingestor_name: str) -> Optional[datetime]:
        """Return the last successful completion time for a date-windowed ingestor."""
        run = await self._find(ingestor_name, cycle=None)
        return run.last_run_completed_at if run else None

    async def has_active_run(self, timeout_minutes: int) -> bool:
        """True if any run is `in_progress` and started within the timeout window."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        stmt = select(IngestionRun).where(
            IngestionRun.status == IngestionRunStatus.IN_PROGRESS,
            IngestionRun.started_at >= cutoff,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None

    async def reset_stale_runs(self, timeout_minutes: int) -> None:
        """Self-heal runs stuck `in_progress` past the timeout, marking them failed."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        stmt = (
            update(IngestionRun)
            .where(
                IngestionRun.status == IngestionRunStatus.IN_PROGRESS,
                IngestionRun.started_at < cutoff,
            )
            .values(
                status=IngestionRunStatus.FAILED,
                error_message="Run exceeded overlap-guard timeout; marked failed.",
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        if result.rowcount:
            logger.warning(
                f"Reset {result.rowcount} stale in-progress ingestion run(s)"
            )

    async def get_ready_cycles(self, required_ingestors: list[str]) -> list[int]:
        """Cycles where every ingestor in `required_ingestors` has EVER
        succeeded, and both spending tables actually have rows for it.

        Deliberately built on `last_run_completed_at` (preserved across a
        later failure) rather than the latest run's `status` — a transient
        error re-ingesting an already-ready cycle (run_nightly re-runs every
        active cycle nightly, not just new ones) would otherwise flip that
        cycle back to not-ready even though its previously-ingested data is
        untouched. The data-existence check separately guards the opposite
        case: a brand-new cycle whose first run "succeeds" with zero records
        (no FEC data yet) must not be reported as ready.

        Hardcodes the two spending tables rather than taking a generic
        ingestor->table mapping — there are only ever these two spending
        ingestors (see SPENDING_INGESTOR_NAMES), so a generic mapping would
        be pure indirection.

        Newest first.
        """
        succeeded_stmt = (
            select(IngestionRun.cycle)
            .where(
                IngestionRun.ingestor_name.in_(required_ingestors),
                IngestionRun.last_run_completed_at.isnot(None),
                IngestionRun.cycle.isnot(None),
            )
            .group_by(IngestionRun.cycle)
            .having(
                func.count(distinct(IngestionRun.ingestor_name))
                == len(required_ingestors)
            )
        )
        result = await self.db.execute(succeeded_stmt)
        candidate_cycles = list(result.scalars().all())
        if not candidate_cycles:
            return []

        inside_stmt = select(InsideTotalsByCandidate.cycle.distinct()).where(
            InsideTotalsByCandidate.cycle.in_(candidate_cycles)
        )
        inside_cycles = set((await self.db.execute(inside_stmt)).scalars().all())

        outside_stmt = select(ScheduleETotalsByCandidate.cycle.distinct()).where(
            ScheduleETotalsByCandidate.cycle.in_(candidate_cycles)
        )
        outside_cycles = set((await self.db.execute(outside_stmt)).scalars().all())

        ready = set(candidate_cycles) & inside_cycles & outside_cycles
        return sorted(ready, reverse=True)
