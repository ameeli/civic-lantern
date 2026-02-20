import asyncio
import logging
from typing import Any, Dict, List, Optional

from civic_lantern.jobs.manager import IngestionManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def ingest(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    entities: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run the FEC ingestion pipeline.

    Args:
        start_date: Start of date range (default: 7 days ago).
        end_date: End of date range (default: today).
        entities: Optional list of entity names to ingest.
            If None, runs all registered entities in dependency order.

    Returns:
        Dict mapping entity names to their ingestion stats (or error info).
    """
    async with IngestionManager() as manager:
        if entities:
            results: Dict[str, Any] = {}
            for name in entities:
                try:
                    results[name] = await manager.ingest(name, start_date, end_date)
                except Exception as e:
                    logger.error(f"Entity '{name}' failed: {e}", exc_info=True)
                    results[name] = {"error": str(e)}
            return results

        return await manager.ingest_all(start_date, end_date)


if __name__ == "__main__":
    asyncio.run(ingest(start_date="2023-01-01", end_date="2023-03-01"))
