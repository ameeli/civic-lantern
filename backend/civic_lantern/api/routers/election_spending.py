from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.api.deps import get_db
from civic_lantern.core.cycles import current_cycle_ceiling
from civic_lantern.jobs.ingestors import SPENDING_INGESTOR_NAMES
from civic_lantern.schemas.election_spending import ElectionSpending
from civic_lantern.services.data.election_spending import ElectionSpendingService
from civic_lantern.services.data.ingestion_run import IngestionRunService

router = APIRouter(prefix="/election-spending", tags=["election_spending"])


def validate_even_cycle(cycle: int = Path(..., ge=1980)) -> int:
    """Dependency to validate that the requested cycle is an even year.

    The upper bound is recomputed on every request (not a frozen module-level
    constant) — otherwise a long-running process started in an odd year would
    permanently reject a newly-active cycle the nightly job has since ingested.
    """
    if cycle % 2 != 0:
        raise HTTPException(
            status_code=422,
            detail=f"Cycle must be an even-numbered year (e.g. 2024). Got {cycle}.",
        )
    max_cycle = current_cycle_ceiling()
    if cycle > max_cycle:
        raise HTTPException(
            status_code=422,
            detail=f"Cycle {cycle} is beyond the current election cycle ({max_cycle}).",
        )
    return cycle


@router.get("", response_model=list[ElectionSpending])
async def get_election_spending(
    db: AsyncSession = Depends(get_db),
) -> list[ElectionSpending]:
    """Fetch election-level spending summaries from the materialized view."""
    service = ElectionSpendingService(db)
    return await service.get_all_spending()


@router.get("/cycles", response_model=list[int])
async def get_ready_election_cycles(
    db: AsyncSession = Depends(get_db),
) -> list[int]:
    """Cycles where every spending ingestor has succeeded, newest first.

    Must be declared before /{cycle} — otherwise Starlette matches "cycles"
    against that path param and 422s trying to parse it as an int.
    """
    service = IngestionRunService(db)
    return await service.get_ready_cycles(SPENDING_INGESTOR_NAMES)


@router.get("/{cycle}", response_model=ElectionSpending)
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
