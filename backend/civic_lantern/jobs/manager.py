import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from civic_lantern.db.session import AsyncSessionLocal
from civic_lantern.jobs.ingestors import INGESTOR_REGISTRY
from civic_lantern.services.fec_client import FECClient

logger = logging.getLogger(__name__)


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

        # Update materialized view only if spending ingestion succeeded
        spending_result = results.get("candidate_spending", {})
        if "candidate_spending" in targets and "error" not in spending_result:
            await self.refresh_spending_stats()

        return results

    async def refresh_spending_stats(self) -> None:
        """Refresh the materialized view for global spending totals."""
        async with AsyncSessionLocal() as session:
            try:
                # CONCURRENTLY allows reads to continue while refreshing
                await session.execute(
                    text(
                        "REFRESH MATERIALIZED VIEW CONCURRENTLY "
                        "mv_election_spending_summary"
                    )
                )
                await session.commit()
                logger.info(
                    "✅ Materialized view 'mv_election_spending_summary' refreshed."
                )
            except Exception as e:
                logger.error(f"Failed to refresh materialized view: {e}", exc_info=True)
                await session.rollback()
