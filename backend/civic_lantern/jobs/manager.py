import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from civic_lantern.core.cycles import active_cycles
from civic_lantern.db.session import AsyncSessionLocal
from civic_lantern.jobs.ingestors import INGESTOR_REGISTRY
from civic_lantern.services.data.ingestion_run import IngestionRunService
from civic_lantern.services.fec_client import FECClient

logger = logging.getLogger(__name__)

# Ingested once per run, no cycle parameter (date-windowed).
DATE_WINDOWED_ENTITIES = ["committees", "candidates"]
# Looped once per active cycle — cycle-scoped snapshot ingestors.
SPENDING_ENTITIES = ["inside_totals_by_candidate", "schedule_e_totals_by_candidate"]
# Comfortably above worst-case run time given the FEC 900/hr rate limit and
# current dataset size; generous enough not to false-positive on a slow FEC day.
OVERLAP_TIMEOUT_MINUTES = 180


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
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """Run a single ingestor by entity name."""
        if self._client is None:
            raise RuntimeError(
                "IngestionManager must be used as an async context manager. "
                "Use 'async with IngestionManager() as manager:'"
            )

        ingestor_cls = INGESTOR_REGISTRY.get(entity)
        if not ingestor_cls:
            raise ValueError(
                f"Unknown entity: '{entity}'. Available: {list(INGESTOR_REGISTRY)}"
            )

        async with AsyncSessionLocal() as session:
            ingestor = ingestor_cls(client=self._client, session=session)
            return await ingestor.run(
                start_date=start_date, end_date=end_date, **kwargs
            )

    async def ingest_batch(
        self,
        entities: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Run ingestors for the given entities, or all if not specified.

        Executes in dependency order. Continues on failure — a failed
        entity is logged and recorded but does not block subsequent ones.
        """
        if entities:
            registry_keys = list(INGESTOR_REGISTRY.keys())
            targets = sorted(entities, key=lambda x: registry_keys.index(x))
        else:
            targets = list(INGESTOR_REGISTRY.keys())

        results: Dict[str, Any] = {}

        for name in targets:
            try:
                results[name] = await self.ingest(name, start_date, end_date, **kwargs)
            except Exception as e:
                logger.error(f"Entity '{name}' failed: {e}", exc_info=True)
                results[name] = {"error": str(e)}

        # Refresh MVs if any spending source ingestor ran and succeeded.
        spending_ingestors = {
            "inside_totals_by_candidate",
            "schedule_e_totals_by_candidate",
        }
        ran = spending_ingestors & set(targets)
        any_succeeded = any(
            results.get(name) and "error" not in results.get(name, {}) for name in ran
        )
        if any_succeeded:
            await self.refresh_spending_stats()

        return results

    async def run_nightly(self) -> Dict[str, Any]:
        """Run the full nightly ingestion routine.

        Date-windowed entities (committees, candidates) run once, resuming
        from their watermark. The two spending-totals ingestors run once per
        active cycle (2024 onward), since they're cycle-scoped snapshots
        rather than date-windowed. Guards against overlapping runs: a recent
        in-progress run blocks this one; a stale one self-heals first.
        """
        async with AsyncSessionLocal() as session:
            guard = IngestionRunService(session)
            if await guard.has_active_run(OVERLAP_TIMEOUT_MINUTES):
                logger.warning("Overlap guard: a run is already in progress, skipping.")
                return {"skipped": "overlap_guard"}
            await guard.reset_stale_runs(OVERLAP_TIMEOUT_MINUTES)

        results: Dict[str, Any] = {}
        results.update(await self.ingest_batch(DATE_WINDOWED_ENTITIES))

        for cycle in active_cycles():
            cycle_results = await self.ingest_batch(SPENDING_ENTITIES, cycle=cycle)
            results.update({f"{name}:{cycle}": r for name, r in cycle_results.items()})

        return results

    async def refresh_spending_stats(self) -> None:
        """Refresh candidate and election spending materialized views.

        mv_candidate_spending_summary must be refreshed before
        mv_election_spending_summary since the latter sources from the former.
        CONCURRENTLY allows reads to continue during each refresh.
        """
        async with AsyncSessionLocal() as session:
            try:
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
            except Exception as e:
                logger.error(
                    f"Failed to refresh materialized views: {e}", exc_info=True
                )
                await session.rollback()
