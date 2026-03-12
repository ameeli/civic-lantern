from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.api.deps import get_db
from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.candidate_spending import CandidateSpendingTotals
from civic_lantern.db.models.enums import OfficeTypeEnum
from civic_lantern.schemas.candidate import CandidateList, CandidateOut, CandidateSortBy
from civic_lantern.schemas.candidate_spending import (
    CandidateSpendingList,
    CandidateSpendingSchema,
    SpendingSortBy,
)
from civic_lantern.services.data.candidate import CandidateService
from civic_lantern.services.data.candidate_spending import CandidateSpendingService

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("/spending", response_model=CandidateSpendingList)
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


@router.get("", response_model=CandidateList)
async def list_candidates(
    state: Optional[str] = Query(
        None, min_length=2, max_length=2, description="2-letter state code"
    ),
    office: Optional[OfficeTypeEnum] = Query(None, description="Office code (P, S, H)"),
    cycle: Optional[int] = Query(None, description="Election cycle year"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort_by: CandidateSortBy = Query("name", description="Field to sort by"),
    order: Literal["asc", "desc"] = Query("asc", description="Sort direction"),
    db: AsyncSession = Depends(get_db),
):
    """
    List candidates with pagination and total count.
    Delegates database logic to CandidateService.
    """
    service = CandidateService(db)

    safe_state = state.upper() if state else None

    return await service.get_list(
        state=safe_state,
        office=office,
        cycle=cycle,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        order=order,
    )


@router.get("/{candidate_id}", response_model=CandidateOut)
async def get_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single candidate by ID."""
    service = CandidateService(db)
    candidate = await service.get_by_id(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@router.get("/{candidate_id}/spending", response_model=list[CandidateSpendingSchema])
async def get_candidate_spending(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch spending totals for a candidate across all cycles."""
    exists = await db.execute(
        select(Candidate.candidate_id).where(Candidate.candidate_id == candidate_id)
    )
    if not exists.scalar():
        raise HTTPException(status_code=404, detail="Candidate not found")

    result = await db.execute(
        select(CandidateSpendingTotals)
        .where(CandidateSpendingTotals.candidate_id == candidate_id)
        .order_by(CandidateSpendingTotals.cycle)
    )
    return result.scalars().all()
