from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.api.deps import get_db
from civic_lantern.schemas.candidate_spending import (
    CandidateSpendingList,
    SpendingSortBy,
)
from civic_lantern.services.data.candidate_spending import CandidateSpendingService

router = APIRouter(prefix="/candidate-spending", tags=["candidate_spending"])


@router.get("", response_model=CandidateSpendingList)
async def list_candidate_spending(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort_by: SpendingSortBy = Query("outside_total", description="Field to sort by"),
    order: Literal["asc", "desc"] = Query("desc", description="Sort direction"),
    db: AsyncSession = Depends(get_db),
):
    """List spending totals for all candidates with pagination."""
    service = CandidateSpendingService(db)
    return await service.get_list(
        limit=limit, offset=offset, sort_by=sort_by, order=order
    )
