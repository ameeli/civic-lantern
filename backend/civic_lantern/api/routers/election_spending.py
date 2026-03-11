import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.api.deps import get_db
from civic_lantern.schemas.election_spending import ElectionSpending

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/elections", tags=["election_spending"])

_current_year = date.today().year
_MAX_CYCLE = _current_year if _current_year % 2 == 0 else _current_year - 1


async def _execute_spending_query(
    db: AsyncSession, query: text, params: dict | None = None
):
    """Execute a spending query, raising HTTP 500 with logging on DB errors."""
    try:
        result = await db.execute(query, params or {})
        return result.mappings()
    except Exception:
        logger.exception("Database error executing election spending query")
        raise HTTPException(
            status_code=500,
            detail="Spending data is currently unavailable. Ensure migrations have run.",
        )


@router.get("/spending", response_model=list[ElectionSpending])
async def get_election_spending(
    db: AsyncSession = Depends(get_db),
) -> list[ElectionSpending]:
    """Fetch election-level spending summaries from the materialized view."""
    mappings = await _execute_spending_query(
        db, text("SELECT * FROM mv_election_spending_summary ORDER BY cycle DESC")
    )
    return mappings.all()


@router.get("/spending/{cycle}", response_model=ElectionSpending)
async def get_election_spending_by_cycle(
    cycle: int = Path(..., ge=1980, le=_MAX_CYCLE),
    db: AsyncSession = Depends(get_db),
) -> ElectionSpending:
    """Fetch spending summary for a specific election cycle."""
    if cycle % 2 != 0:
        raise HTTPException(
            status_code=422,
            detail=f"Cycle must be an even-numbered year (e.g. 2024). Got {cycle}.",
        )

    mappings = await _execute_spending_query(
        db,
        text("SELECT * FROM mv_election_spending_summary WHERE cycle = :cycle"),
        {"cycle": cycle},
    )
    row = mappings.first()

    if not row:
        raise HTTPException(
            status_code=404, detail=f"No data found for the {cycle} election cycle."
        )

    return row
