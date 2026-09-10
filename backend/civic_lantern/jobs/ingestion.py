import argparse
import asyncio
import logging
import signal
import sys
from typing import Any, Awaitable, Dict, List, Optional, Sequence, TypeVar

from civic_lantern.jobs.manager import IngestionManager
from civic_lantern.utils.logging import configure_logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


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


async def _run_cancellable(coro: Awaitable[T]) -> T:
    """Run `coro`, translating SIGTERM into task cancellation instead of an
    abrupt process kill.

    GitHub Actions sends SIGTERM (then SIGKILL ~7.5s later) when a workflow
    run is cancelled. Without a handler, Python has no default response to
    SIGTERM at all — the process just dies mid-await, and BaseIngestor.run()
    never gets a chance to mark its `ingestion_runs` row as anything other
    than IN_PROGRESS. Cancelling the task instead raises CancelledError at
    the current await point, which propagates up through BaseIngestor.run()'s
    own CancelledError handler before this function re-raises it.
    """
    task = asyncio.ensure_future(coro)
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGTERM, task.cancel)
    except NotImplementedError:
        pass  # e.g. Windows' default event loop doesn't support this

    try:
        return await task
    except asyncio.CancelledError:
        logger.warning("Ingestion run cancelled (SIGTERM)")
        raise
    finally:
        try:
            loop.remove_signal_handler(signal.SIGTERM)
        except NotImplementedError:
            pass


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
    try:
        if args.entities:
            entities = [e.strip() for e in args.entities.split(",") if e.strip()]
            kwargs = {"cycle": args.cycle} if args.cycle else {}
            results = asyncio.run(_run_cancellable(ingest(entities=entities, **kwargs)))
        else:
            results = asyncio.run(_run_cancellable(run_nightly()))
    except asyncio.CancelledError:
        sys.exit(1)

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
