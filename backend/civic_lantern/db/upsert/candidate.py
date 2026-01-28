import logging
from typing import Any, Dict, List

from sqlalchemy import exc
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.schemas.candidate import CandidateIn

logger = logging.getLogger(__name__)


async def upsert_candidates(
    db: AsyncSession, candidates: List[CandidateIn], batch_size: int = 1000
) -> Dict[str, Any]:
    """
    Upserts candidates in batches. If a batch fails, falls back to row-by-row
    processing to identify specific errors without losing valid data.

    Args:
        db: Database session
        candidates: List of validated CandidateIn instances
        batch_size: Number of records to process in one transaction

    Returns:
        Dict containing counts of successes, failures, and a list of failed IDs.
    """
    if not candidates:
        logger.info("No candidates to upsert")
        return {"upserted": 0, "errors": 0, "failed_ids": []}

    candidate_data = [c.model_dump() for c in candidates]

    stats = {"upserted": 0, "errors": 0, "failed_ids": []}

    for i in range(0, len(candidate_data), batch_size):
        batch = candidate_data[i : i + batch_size]

        try:
            await _execute_upsert(db, batch)
            await db.commit()

            stats["upserted"] += len(batch)
            logger.debug(f"Successfully committed batch of {len(batch)} candidates")

        except exc.SQLAlchemyError as e:
            await db.rollback()

            logger.warning(
                f"Batch failed (index {i}-{i + len(batch)}). "
                f"Switching to row-by-row processing. Error: {e}"
            )

            batch_stats = await _process_batch_individually(db, batch)

            stats["upserted"] += batch_stats["success_count"]
            stats["errors"] += batch_stats["error_count"]
            stats["failed_ids"].extend(batch_stats["failed_ids"])

    logger.info(
        f"Upsert complete. Success: {stats['upserted']}, Errors: {stats['errors']}"
    )
    return stats


async def _process_batch_individually(
    db: AsyncSession, batch: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Helper to process a failed batch one row at a time to isolate bad data.
    """
    stats = {"success_count": 0, "error_count": 0, "failed_ids": []}

    for row in batch:
        candidate_id = row.get("candidate_id", "UNKNOWN_ID")

        try:
            async with db.begin_nested():
                await _execute_upsert(db, [row])

            stats["success_count"] += 1
            logger.debug(f"Successfully upserted candidate_id '{candidate_id}'")

        except Exception as row_error:
            stats["error_count"] += 1
            stats["failed_ids"].append(candidate_id)

            logger.error(
                f"Failed to upsert candidate_id '{candidate_id}': {row_error}",
                extra={"candidate_data": row},
            )

    await db.commit()

    logger.info(
        f"Row-by-row processing complete: "
        f"{stats['success_count']} succeeded, {stats['error_count']} failed"
    )

    return stats


async def _execute_upsert(db: AsyncSession, values: List[Dict[str, Any]]) -> None:
    """
    Constructs and executes the PostgreSQL upsert statement.
    Separated for clarity and testing.
    """
    stmt = insert(Candidate).values(values)

    update_cols = {col.name: col for col in stmt.excluded if col.name != "candidate_id"}

    stmt = stmt.on_conflict_do_update(
        index_elements=["candidate_id"],
        set_=update_cols,
    )

    await db.execute(stmt)
