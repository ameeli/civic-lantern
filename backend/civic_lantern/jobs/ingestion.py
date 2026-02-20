import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from civic_lantern.jobs.manager import IngestionManager

FEC_TIMEZONE = ZoneInfo("America/New_York")


class _EasternFormatter(logging.Formatter):
    """Log formatter that renders timestamps in US/Eastern with offset."""

    def formatTime(self, record: logging.LogRecord, datefmt: str = None) -> str:
        utc_dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        et_dt = utc_dt.astimezone(FEC_TIMEZONE)
        if datefmt:
            return et_dt.strftime(datefmt)
        return et_dt.isoformat()


_handler = logging.StreamHandler()
_handler.setFormatter(
    _EasternFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
)
logging.basicConfig(level=logging.INFO, handlers=[_handler])


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
        return await manager.ingest_batch(entities, start_date, end_date)


if __name__ == "__main__":
    asyncio.run(ingest(start_date="2023-06-01", end_date="2023-08-01"))
