from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.api.deps import get_db
from civic_lantern.schemas.election_spending import ElectionSpending
from civic_lantern.services.data.election_spending import ElectionSpendingService

router = APIRouter(prefix="/elections", tags=["election_spending"])

_current_year = date.today().year
_MAX_CYCLE = _current_year if _current_year % 2 == 0 else _current_year - 1


def validate_even_cycle(cycle: int = Path(..., ge=1980, le=_MAX_CYCLE)) -> int:
    """Dependency to validate that the requested cycle is an even year."""
    if cycle % 2 != 0:
        raise HTTPException(
            status_code=422,
            detail=f"Cycle must be an even-numbered year (e.g. 2024). Got {cycle}.",
        )
    return cycle


@router.get("/spending", response_model=list[ElectionSpending])
async def get_election_spending(
    db: AsyncSession = Depends(get_db),
) -> list[ElectionSpending]:
    """Fetch election-level spending summaries from the materialized view."""
    service = ElectionSpendingService(db)
    return await service.get_all_spending()


@router.get("/spending/{cycle}", response_model=ElectionSpending)
async def get_election_spending_by_cycle(
    cycle: int = Depends(validate_even_cycle),
    db: AsyncSession = Depends(get_db),
) -> ElectionSpending:
    """Fetch spending summary for a specific election cycle."""
    service = ElectionSpendingService(db)
    row = await service.get_spending_by_cycle(cycle)

    if not row:
        raise HTTPException(
            status_code=404, detail=f"No data found for the {cycle} election cycle."
        )

    return row
