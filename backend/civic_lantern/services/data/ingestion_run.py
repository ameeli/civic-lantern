import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional, Sequence, cast

from sqlalchemy import CursorResult, distinct, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.ingestion_run import IngestionRun, IngestionRunStatus
from civic_lantern.services.data.base import BaseService

if TYPE_CHECKING:
    from civic_lantern.jobs.pipeline import Ingestion

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
        result = cast(CursorResult, await self.db.execute(stmt))
        await self.db.commit()
        if result.rowcount:
            logger.warning(
                f"Reset {result.rowcount} stale in-progress ingestion run(s)"
            )

    async def get_ready_cycles(self, required: Sequence["Ingestion"]) -> list[int]:
        """Cycles where every ingestion in `required` has EVER succeeded, and
        each one's table actually has rows for it. Newest first.

        Deliberately built on `last_run_completed_at` (preserved across a
        later failure) rather than the latest run's `status` — a transient
        error re-ingesting an already-ready cycle (run_nightly re-runs every
        active cycle nightly, not just new ones) would otherwise flip that
        cycle back to not-ready even though its previously-ingested data is
        untouched. The data-existence check separately guards the opposite
        case: a brand-new cycle whose first run "succeeds" with zero records
        (no FEC data yet) must not be reported as ready.
        """
        names = [ingestion.entity for ingestion in required]
        succeeded_stmt = (
            select(IngestionRun.cycle)
            .where(
                IngestionRun.ingestor_name.in_(names),
                IngestionRun.last_run_completed_at.isnot(None),
                IngestionRun.cycle.isnot(None),
            )
            .group_by(IngestionRun.cycle)
            .having(func.count(distinct(IngestionRun.ingestor_name)) == len(names))
        )
        ready = set((await self.db.execute(succeeded_stmt)).scalars().all())
        for ingestion in required:
            if not ready:
                break
            cycle_col = ingestion.model.cycle
            with_rows = select(cycle_col.distinct()).where(cycle_col.in_(ready))
            ready &= set((await self.db.execute(with_rows)).scalars().all())
        # The query filters IngestionRun.cycle.isnot(None); mypy can't know that.
        return sorted((c for c in ready if c is not None), reverse=True)
