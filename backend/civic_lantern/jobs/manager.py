import logging
from typing import Any, Dict, Optional

from civic_lantern.db.session import AsyncSessionLocal
from civic_lantern.jobs.ingestors import INGESTOR_REGISTRY
from civic_lantern.services.fec_client import FECClient

logger = logging.getLogger(__name__)


class IngestionManager:
    """Owns the shared FECClient lifecycle and routes to ingestors.

    Usage::

        async with IngestionManager() as manager:
            await manager.ingest_all()                          # all entities
            await manager.ingest("candidates", start_date=...) # single entity
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
        registry = dict(INGESTOR_REGISTRY)
        ingestor_cls = registry.get(entity)
        if not ingestor_cls:
            raise ValueError(
                f"Unknown entity: '{entity}'. "
                f"Available: {[name for name, _ in INGESTOR_REGISTRY]}"
            )

        async with AsyncSessionLocal() as session:
            ingestor = ingestor_cls(client=self._client, session=session)
            return await ingestor.run(start_date, end_date, **kwargs)

    async def ingest_all(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run all registered ingestors in dependency order.

        Continues on failure — a failed entity is logged and recorded
        in the results dict, but does not block subsequent entities.
        """
        results: Dict[str, Any] = {}

        for name, _ in INGESTOR_REGISTRY:
            try:
                results[name] = await self.ingest(name, start_date, end_date)
            except Exception as e:
                logger.error(f"Entity '{name}' failed: {e}", exc_info=True)
                results[name] = {"error": str(e)}

        return results
