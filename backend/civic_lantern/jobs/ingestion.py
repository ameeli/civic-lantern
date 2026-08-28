import asyncio
import logging
import sys
from typing import Any, Dict, List, Optional

from civic_lantern.jobs.manager import IngestionManager
from civic_lantern.utils.logging import configure_logging

logger = logging.getLogger(__name__)


async def ingest(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    entities: Optional[List[str]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Run a single ingestion pass over the given entities (ad hoc / manual use).

    Args:
        start_date: Start of date range (default: resumes from watermark).
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


async def run_nightly() -> Dict[str, Any]:
    """Run the full nightly routine: date-windowed entities once, spending
    entities once per active cycle. See IngestionManager.run_nightly()."""
    async with IngestionManager() as manager:
        return await manager.run_nightly()


def main() -> None:
    """CLI entrypoint for the nightly GitHub Actions workflow."""
    configure_logging()
    results = asyncio.run(run_nightly())

    failed = [
        name
        for name, result in results.items()
        if isinstance(result, dict) and "error" in result
    ]
    if failed:
        logger.error(f"Ingestion completed with failures: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
