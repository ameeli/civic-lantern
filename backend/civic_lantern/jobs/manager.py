import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from civic_lantern.core.cycles import active_cycles
from civic_lantern.db.session import JobSessionLocal
from civic_lantern.jobs.ingestors import (
    DATE_WINDOW_INGESTIONS,
    INGESTIONS,
    INGESTIONS_BY_NAME,
    SPENDING_INGESTOR_NAMES,
)
from civic_lantern.jobs.pipeline import run_ingestion
from civic_lantern.services.data.base import UpsertStats
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
# Result key for a failed MV refresh, so the CLI counts it as a failure.
MV_REFRESH_RESULT_KEY = "refresh_spending_stats"


class IngestionManager:
    """Owns the shared FECClient lifecycle and routes to ingestors.

    Usage::

        async with IngestionManager() as manager:
            await manager.ingest_batch()                             # all entities
            await manager.ingest_batch(["candidates"])              # subset
            await manager.ingest("candidates", start_date=...)  # single entity
    """

    def __init__(self) -> None:
        self._client: Optional[FECClient] = None

    async def __aenter__(self) -> "IngestionManager":
        self._client = FECClient()
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)

    async def ingest(
        self,
        entity: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        cycle: Optional[int] = None,
    ) -> Optional[UpsertStats]:
        """Run one entity's ingestion by name."""
        if self._client is None:
            raise RuntimeError(
                "IngestionManager must be used as an async context manager. "
                "Use 'async with IngestionManager() as manager:'"
            )

        ingestion = INGESTIONS_BY_NAME.get(entity)
        if ingestion is None:
            raise ValueError(_unknown_entity(entity))

        async with JobSessionLocal() as session:
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
        skip_mv_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Run ingestors for the given entities, or all if not specified.

        Executes in dependency order. Continues on failure — a failed
        entity is logged and recorded but does not block subsequent ones.

        `skip_mv_refresh` lets a caller defer the MV refresh across several
        calls (e.g. run_nightly()'s per-cycle loop) so it happens once
        overall rather than once per call — the MVs span every cycle, so
        refreshing after each individual cycle is redundant work.
        """
        unknown = [e for e in entities or [] if e not in INGESTIONS_BY_NAME]
        if unknown:
            raise ValueError(_unknown_entity(unknown[0]))
        targets = [i.entity for i in INGESTIONS if not entities or i.entity in entities]

        results: Dict[str, Any] = {}

        for name in targets:
            try:
                results[name] = await self.ingest(name, start_date, end_date, cycle)
            except Exception as e:
                logger.error(f"Entity '{name}' failed: {e}", exc_info=True)
                results[name] = {"error": str(e)}

        # Refresh MVs if any spending source ingestor ran and succeeded.
        ran = set(SPENDING_INGESTOR_NAMES) & set(targets)
        any_succeeded = any(
            results.get(name) and "error" not in results.get(name, {}) for name in ran
        )
        if any_succeeded and not skip_mv_refresh:
            await self._refresh_recording_errors(results)

        return results

    async def run_nightly(self) -> Dict[str, Any]:
        """Run the full nightly ingestion routine.

        Date-windowed entities (committees, candidates) run once, resuming
        from their watermark. The two spending-totals ingestors run once per
        active cycle (2024 onward), since they're cycle-scoped snapshots
        rather than date-windowed. Guards against overlapping runs: a recent
        in-progress run blocks this one; a stale one self-heals first.
        """
        async with JobSessionLocal() as session:
            guard = IngestionRunService(session)
            if await guard.has_active_run(OVERLAP_TIMEOUT_MINUTES):
                logger.warning("Overlap guard: a run is already in progress, skipping.")
                return {"skipped": "overlap_guard"}
            await guard.reset_stale_runs(OVERLAP_TIMEOUT_MINUTES)

        results: Dict[str, Any] = {}
        results.update(await self.ingest_batch(DATE_WINDOWED_ENTITIES))

        any_spending_succeeded = False
        for cycle in active_cycles():
            cycle_results = await self.ingest_batch(
                SPENDING_ENTITIES, cycle=cycle, skip_mv_refresh=True
            )
            results.update({f"{name}:{cycle}": r for name, r in cycle_results.items()})
            any_spending_succeeded = any_spending_succeeded or any(
                r and "error" not in r for r in cycle_results.values()
            )

        # One refresh for the whole run, not once per active cycle — the MVs
        # span every cycle, so refreshing after each is redundant work that
        # grows every time another cycle becomes active.
        if any_spending_succeeded:
            await self._refresh_recording_errors(results)

        return results

    async def refresh_spending_stats(self) -> None:
        """Refresh candidate and election spending materialized views.

        mv_candidate_spending_summary must be refreshed before
        mv_election_spending_summary since the latter sources from the former.
        CONCURRENTLY allows reads to continue during each refresh. Raises on
        failure; closing the session rolls back.
        """
        async with JobSessionLocal() as session:
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

    async def _refresh_recording_errors(self, results: Dict[str, Any]) -> None:
        """Refresh the MVs, recording a failure in `results` instead of raising."""
        try:
            await self.refresh_spending_stats()
        except Exception as e:
            logger.error(f"Failed to refresh materialized views: {e}", exc_info=True)
            results[MV_REFRESH_RESULT_KEY] = {"error": str(e)}


def _unknown_entity(entity: str) -> str:
    return f"Unknown entity: '{entity}'. Available: {list(INGESTIONS_BY_NAME)}"
