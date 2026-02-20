import logging
from typing import Any, Dict, List, Optional

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
        ingestor_cls = INGESTOR_REGISTRY.get(entity)
        if not ingestor_cls:
            raise ValueError(
                f"Unknown entity: '{entity}'. "
                f"Available: {list(INGESTOR_REGISTRY)}"
            )

        async with AsyncSessionLocal() as session:
            ingestor = ingestor_cls(client=self._client, session=session)
            return await ingestor.run(start_date, end_date, **kwargs)

    async def ingest_batch(
        self,
        entities: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run ingestors for the given entities, or all if not specified.

        Executes in dependency order. Continues on failure — a failed
        entity is logged and recorded but does not block subsequent ones.
        """
        targets = entities if entities else list(INGESTOR_REGISTRY)
        results: Dict[str, Any] = {}

        for name in targets:
            try:
                results[name] = await self.ingest(name, start_date, end_date)
            except Exception as e:
                logger.error(f"Entity '{name}' failed: {e}", exc_info=True)
                results[name] = {"error": str(e)}

        return results
