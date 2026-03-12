from typing import Any, Literal, Optional

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.enums import OfficeTypeEnum
from civic_lantern.schemas.candidate import CandidateSortBy
from civic_lantern.services.data.base import BaseService


class CandidateService(BaseService[Candidate]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(model=Candidate, db=db)

    def _build_base_query(
        self,
        state: Optional[str] = None,
        office: Optional[OfficeTypeEnum] = None,
        cycle: Optional[int] = None,
    ):
        """Pure logic: builds the filtered SELECT statement."""
        stmt = select(Candidate)
        if state:
            stmt = stmt.where(Candidate.state == state)
        if office:
            stmt = stmt.where(Candidate.office == office)
        if cycle:
            stmt = stmt.where(Candidate.cycles.contains([cycle]))
        return stmt

    def _apply_sorting(
        self, stmt, sort_by: CandidateSortBy, order: Literal["asc", "desc"]
    ):
        """Pure logic: appends ORDER BY clauses."""
        sort_options = {
            "name": Candidate.name,
            "state": Candidate.state,
            "first_file_date": Candidate.first_file_date,
            "last_file_date": Candidate.last_file_date,
        }
        column = sort_options[sort_by]

        direction = desc if order == "desc" else asc
        # Use candidate ID as tiebreaker for stable pagination
        return stmt.order_by(direction(column), Candidate.candidate_id)

    async def get_list(
        self,
        state: Optional[str],
        office: Optional[OfficeTypeEnum],
        cycle: Optional[int],
        limit: int = 100,
        offset: int = 0,
        sort_by: CandidateSortBy = "name",
        order: Literal["asc", "desc"] = "desc",
    ) -> dict[str, Any]:
        """Orchestrator: Coordinates building, counting, and fetching."""
        base_query = self._build_base_query(state, office, cycle)

        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_count = (await self.db.execute(count_stmt)).scalar() or 0

        sorted_query = self._apply_sorting(base_query, sort_by, order)
        final_query = sorted_query.limit(limit).offset(offset)

        result = await self.db.execute(final_query)

        return {
            "items": result.scalars().all(),
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }
