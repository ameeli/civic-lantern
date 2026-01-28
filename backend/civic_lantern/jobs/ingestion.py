import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from civic_lantern.db.session import AsyncSessionLocal
from civic_lantern.db.upsert.candidate import upsert_candidates
from civic_lantern.services.fec_client import FECClient
from civic_lantern.utils.transformers import transform_candidates

logger = logging.getLogger(__name__)


async def ingest_candidates(
    start_date: Optional[str] = None, end_date: Optional[str] = None
):
    """Import candidates from FEC API."""
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    async with FECClient() as client:
        logger.info(f"Syncing candidates from {start_date} to {end_date}")
        raw_candidates = await client.get_candidates(
            election_year=2024,
            min_first_file_date=start_date,
            max_first_file_date=end_date,
            sort="-first_file_date",
        )
        transformed_candidates = transform_candidates(raw_candidates)

        if not transformed_candidates:
            logger.info("No candidates found to ingest.")
            return

        async with AsyncSessionLocal() as db:
            results = await upsert_candidates(
                db=db,
                candidates=transformed_candidates,
                batch_size=500,
            )
            await db.commit()

            print(f"Ingestion complete for {start_date} to {end_date}")
            print(f" - Successfully upserted: {results['upserted']}")
            print(f" - Errors encountered: {results['errors']}")

            if results["failed_ids"]:
                print(f" - Sample of failed IDs: {results['failed_ids'][:5]}")


if __name__ == "__main__":
    asyncio.run(ingest_candidates(start_date="2024-01-01", end_date="2024-01-02"))
