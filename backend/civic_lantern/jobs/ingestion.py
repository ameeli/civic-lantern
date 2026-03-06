import asyncio
from typing import Any, Dict, List, Optional

from civic_lantern.jobs.manager import IngestionManager
from civic_lantern.utils.logging import configure_logging

# TODO: When you add main.py as part of HTTP server, move this line to that file
configure_logging()


async def ingest(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    entities: Optional[List[str]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Run the FEC ingestion pipeline.

    Args:
        start_date: Start of date range (default: 7 days ago).
        end_date: End of date range (default: today).
        entities: Optional list of entity names to ingest.
            If None, runs all registered entities in dependency order.
        **kwargs: Additional params forwarded to each ingestor's fetch()
            (e.g. cycle=2024 for spending ingestors).

    Returns:
        Dict mapping entity names to their ingestion stats (or error info).
    """
    async with IngestionManager() as manager:
        return await manager.ingest_batch(entities, start_date, end_date, **kwargs)


if __name__ == "__main__":
    asyncio.run(
        ingest(
            cycle=2024,
            entities=["candidate_spending"],
        )
    )
