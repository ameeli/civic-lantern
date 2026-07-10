from typing import Any, Literal, Sequence

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.mv_candidate_spending_summary import (
    MvCandidateSpendingSummary,
)
from civic_lantern.schemas.candidate_spending import SpendingSortBy
from civic_lantern.services.data.base import BaseService


class CandidateSpendingService(BaseService[MvCandidateSpendingSummary]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(model=MvCandidateSpendingSummary, db=db)
        self.index_elements = ["candidate_id", "cycle"]

    def _build_base_query(self) -> Any:
        return select(MvCandidateSpendingSummary)

    def _apply_sorting(
        self,
        stmt: Any,
        sort_by: SpendingSortBy,
        order: Literal["asc", "desc"],
    ) -> Any:
        sort_options = {
            "cycle": MvCandidateSpendingSummary.cycle,
            "inside_receipts": MvCandidateSpendingSummary.inside_receipts,
            "inside_disbursements": MvCandidateSpendingSummary.inside_disbursements,
            "outside_support": MvCandidateSpendingSummary.outside_support,
            "outside_oppose": MvCandidateSpendingSummary.outside_oppose,
            "outside_total": MvCandidateSpendingSummary.outside_support
            + MvCandidateSpendingSummary.outside_oppose,
            "influence_ratio": MvCandidateSpendingSummary.influence_ratio,
            "vulnerability_factor": MvCandidateSpendingSummary.vulnerability_factor,
        }
        sort_column = sort_options[sort_by]
        direction = desc if order == "desc" else asc
        return stmt.order_by(
            direction(sort_column),
            MvCandidateSpendingSummary.candidate_id,
            MvCandidateSpendingSummary.cycle,
        )

    async def _attach_candidates(self, items: list) -> None:
        """Fetch candidate info for a page of MV rows and attach as .candidate.

        MvCandidateSpendingSummary is on ViewBase so it cannot carry a SQLAlchemy
        relationship to Candidate (different declarative registry). A secondary
        IN query keeps this to two round-trips per page.
        """
        if not items:
            return
        candidate_ids = [item.candidate_id for item in items]
        result = await self.db.execute(
            select(Candidate).where(Candidate.candidate_id.in_(candidate_ids))
        )
        candidate_map = {c.candidate_id: c for c in result.scalars().all()}
        for item in items:
            item.candidate = candidate_map.get(item.candidate_id)

    async def get_list(
        self,
        limit: int = 100,
        offset: int = 0,
        sort_by: SpendingSortBy = "outside_total",
        order: Literal["asc", "desc"] = "desc",
    ) -> dict[str, Any]:
        base_stmt = self._build_base_query()

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_count = (await self.db.execute(count_stmt)).scalar() or 0

        data_stmt = (
            self._apply_sorting(base_stmt, sort_by, order).limit(limit).offset(offset)
        )
        result = await self.db.execute(data_stmt)
        items = list(result.scalars().all())

        await self._attach_candidates(items)

        return {
            "items": items,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }

    async def get_spending_by_candidate_id(
        self, candidate_id: str
    ) -> Sequence[MvCandidateSpendingSummary]:
        stmt = (
            select(MvCandidateSpendingSummary)
            .where(MvCandidateSpendingSummary.candidate_id == candidate_id)
            .order_by(desc(MvCandidateSpendingSummary.cycle))
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        await self._attach_candidates(items)
        return items
