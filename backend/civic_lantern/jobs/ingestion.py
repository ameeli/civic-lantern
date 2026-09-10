import argparse
import asyncio
import logging
import sys
from typing import Any, Dict, List, Optional, Sequence

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


def main(argv: Optional[Sequence[str]] = None) -> None:
    """CLI entrypoint for both the nightly GitHub Actions workflow (no args)
    and manually-triggered one-off runs (--entities/--cycle).

    `argv` defaults to None, which tells argparse to read `sys.argv[1:]` —
    pass an explicit list (e.g. []) in tests to avoid parsing pytest's own
    command-line arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--entities", help="Comma-separated entity names")
    parser.add_argument("--cycle", type=int, help="Cycle year, if applicable")
    args = parser.parse_args(argv)

    configure_logging()
    if args.entities:
        entities = [e.strip() for e in args.entities.split(",") if e.strip()]
        kwargs = {"cycle": args.cycle} if args.cycle else {}
        results = asyncio.run(ingest(entities=entities, **kwargs))
    else:
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
