import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from civic_lantern.core.cycles import active_cycles
from civic_lantern.db.models.ingestion_run import IngestionRunStatus
from civic_lantern.jobs.ingestors import (
    DATE_WINDOW_INGESTIONS,
    INGESTIONS,
    INGESTIONS_BY_NAME,
    SPENDING_INGESTOR_NAMES,
)
from civic_lantern.jobs.pipeline import RunOutcome, run_ingestion
from civic_lantern.services.data.ingestion_run import IngestionRunService
from civic_lantern.services.fec_client import FECClient

logger = logging.getLogger(__name__)

# Ingested once per run, resuming from the watermark.
DATE_WINDOWED_ENTITIES = [i.entity for i in DATE_WINDOW_INGESTIONS]
# Looped once per active cycle.
SPENDING_ENTITIES = SPENDING_INGESTOR_NAMES
# Generous enough to never false-positive on a legitimately slow run — in
# particular, an entity's very first date-window run does a full, unfiltered
# historical pull (see pipeline._date_window_params) that can take several
# hours under the FEC 900/hr rate limit. Still self-heals well before the
# next night's scheduled trigger.
OVERLAP_TIMEOUT_MINUTES = 720
# How a failed MV refresh is named in a RunReport.
MV_REFRESH_LABEL = "refresh_spending_stats"

RunKey = Tuple[str, Optional[int]]


@dataclass
class RunReport:
    """What one manager call did: each run's outcome by (entity, cycle), in run
    order, plus whether the overlap guard skipped it and any MV refresh error."""

    outcomes: Dict[RunKey, RunOutcome] = field(default_factory=dict)
    skipped: bool = False
    mv_refresh_error: Optional[str] = None

    @property
    def failed(self) -> List[str]:
        """Labels of the failed runs, plus the MV refresh if it failed."""
        failed = [
            _label(key)
            for key, outcome in self.outcomes.items()
            if outcome.status == IngestionRunStatus.FAILED
        ]
        if self.mv_refresh_error is not None:
            failed.append(MV_REFRESH_LABEL)
        return failed

    @property
    def needs_mv_refresh(self) -> bool:
        """The MVs read only spending tables: refresh if a spending run wrote rows."""
        return any(
            entity in SPENDING_INGESTOR_NAMES and outcome.wrote_rows
            for (entity, _), outcome in self.outcomes.items()
        )

    def summary(self) -> str:
        """One line per run (and the MV refresh if it failed), for the CLI log."""
        if self.skipped:
            return "Ingestion skipped: another run is in progress."
        if not self.outcomes:
            return "Ingestion summary: nothing ran."
        lines = [
            (_label(key), outcome.status.value, _detail(outcome))
            for key, outcome in self.outcomes.items()
        ]
        if self.mv_refresh_error is not None:
            lines.append((MV_REFRESH_LABEL, "failed", self.mv_refresh_error))
        width = max(len(label) for label, _, _ in lines)
        rows = [
            f"  {label:<{width}}  {status:<15}  {detail}".rstrip()
            for label, status, detail in lines
        ]
        return "\n".join(["Ingestion summary:", *rows])


class IngestionManager:
    """Runs ingestions by name, in dependency order, with the given FEC client
    and session factory.

    Usage::

        manager = IngestionManager(client, JobSessionLocal)
        await manager.run_nightly()                       # the nightly routine
        await manager.ingest_batch(["candidates"])        # a subset
        await manager.ingest("candidates", start_date=...)  # one entity
    """

    def __init__(
        self, client: FECClient, sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        self._client = client
        self._sessions = sessions

    async def ingest(
        self,
        entity: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        cycle: Optional[int] = None,
    ) -> RunOutcome:
        """Run one entity's ingestion by name; raises if the run fails."""
        ingestion = INGESTIONS_BY_NAME.get(entity)
        if ingestion is None:
            raise ValueError(_unknown_entity(entity))

        async with self._sessions() as session:
            return await run_ingestion(
                ingestion,
                self._client,
                session,
                cycle=cycle,
                start_date=start_date,
                end_date=end_date,
            )

    async def ingest_batch(
        self,
        entities: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        *,
        cycle: Optional[int] = None,
    ) -> RunReport:
        """Run the given entities, or all if not specified, in dependency
        order, then refresh the MVs if needed.

        Continues on failure — a failed entity is logged and recorded as
        FAILED in the report but does not block subsequent ones.
        """
        unknown = [e for e in entities or [] if e not in INGESTIONS_BY_NAME]
        if unknown:
            raise ValueError(_unknown_entity(unknown[0]))
        targets = [i.entity for i in INGESTIONS if not entities or i.entity in entities]

        report = RunReport()
        await self._run_all(report, targets, cycle, start_date, end_date)
        await self._refresh_if_needed(report)
        return report

    async def run_nightly(self) -> RunReport:
        """Run the full nightly ingestion routine.

        Date-windowed entities (committees, candidates) run once, resuming
        from their watermark. The two spending-totals ingestors run once per
        active cycle (2024 onward), since they're cycle-scoped snapshots
        rather than date-windowed. Guards against overlapping runs: a recent
        in-progress run blocks this one; a stale one self-heals first.
        """
        async with self._sessions() as session:
            guard = IngestionRunService(session)
            if await guard.has_active_run(OVERLAP_TIMEOUT_MINUTES):
                logger.warning("Overlap guard: a run is already in progress, skipping.")
                return RunReport(skipped=True)
            await guard.reset_stale_runs(OVERLAP_TIMEOUT_MINUTES)

        report = RunReport()
        await self._run_all(report, DATE_WINDOWED_ENTITIES)
        for cycle in active_cycles():
            await self._run_all(report, SPENDING_ENTITIES, cycle)

        # One refresh for the whole run, not once per active cycle — the MVs
        # span every cycle, so refreshing after each is redundant work that
        # grows every time another cycle becomes active.
        await self._refresh_if_needed(report)
        return report

    async def refresh_spending_stats(self) -> None:
        """Refresh candidate and election spending materialized views.

        mv_candidate_spending_summary must be refreshed before
        mv_election_spending_summary since the latter sources from the former.
        CONCURRENTLY allows reads to continue during each refresh. Raises on
        failure; closing the session rolls back.
        """
        async with self._sessions() as session:
            await session.execute(
                text(
                    "REFRESH MATERIALIZED VIEW CONCURRENTLY "
                    "mv_candidate_spending_summary"
                )
            )
            await session.execute(
                text(
                    "REFRESH MATERIALIZED VIEW CONCURRENTLY "
                    "mv_election_spending_summary"
                )
            )
            await session.commit()
            logger.info("✅ Materialized views refreshed.")

    async def _run_all(
        self,
        report: RunReport,
        entities: Sequence[str],
        cycle: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> None:
        """Run each entity in order, recording a raised error as FAILED."""
        for name in entities:
            try:
                outcome = await self.ingest(name, start_date, end_date, cycle)
            except Exception as e:
                logger.error(
                    f"Entity '{_label((name, cycle))}' failed: {e}", exc_info=True
                )
                outcome = RunOutcome(IngestionRunStatus.FAILED, error=str(e))
            report.outcomes[(name, cycle)] = outcome

    async def _refresh_if_needed(self, report: RunReport) -> None:
        """Refresh the MVs if the report calls for it, recording a failure in
        the report instead of raising."""
        if not report.needs_mv_refresh:
            return
        try:
            await self.refresh_spending_stats()
        except Exception as e:
            logger.error(f"Failed to refresh materialized views: {e}", exc_info=True)
            report.mv_refresh_error = str(e)


def _label(key: RunKey) -> str:
    entity, cycle = key
    return entity if cycle is None else f"{entity}:{cycle}"


def _detail(outcome: RunOutcome) -> str:
    parts = []
    if outcome.stats is not None:
        stats = outcome.stats
        parts.append(
            f"inserted={stats['inserted']} updated={stats['updated']} "
            f"errors={stats['errors']}"
        )
    if outcome.error:
        parts.append(outcome.error)
    return "  ".join(parts)


def _unknown_entity(entity: str) -> str:
    return f"Unknown entity: '{entity}'. Available: {list(INGESTIONS_BY_NAME)}"
