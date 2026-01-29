import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from civic_lantern.db.session import AsyncSessionLocal
from civic_lantern.services.data.candidate import CandidateService
from civic_lantern.services.fec_client import FECClient
from civic_lantern.utils.transformers import transform_candidates

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
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
        # NOTE: only want to open this once, pass client to later ingestion scripts
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

        async with AsyncSessionLocal() as session:
            candidate_service = CandidateService(db=session)

            try:
                stats = await candidate_service.upsert_batch(transformed_candidates)

                logger.info(f"Ingestion complete for {start_date} to {end_date}")
                logger.info(f"Success: {stats['upserted']}")
                logger.info(f"Errors:  {stats['errors']}")

                return stats
            except Exception as e:
                logger.error(f"❌ Ingestion failed: {e}", exc_info=True)
                raise


if __name__ == "__main__":
    asyncio.run(ingest_candidates(start_date="2024-01-10", end_date="2024-01-31"))
