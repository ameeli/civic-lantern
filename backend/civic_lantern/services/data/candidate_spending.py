from typing import Any, Literal

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from civic_lantern.db.models.candidate_spending import CandidateSpendingTotals
from civic_lantern.schemas.candidate_spending import SpendingSortBy
from civic_lantern.services.data.base import BaseService


class CandidateSpendingService(BaseService[CandidateSpendingTotals]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(model=CandidateSpendingTotals, db=db)
        self.index_elements = ["candidate_id", "cycle"]

    def _build_base_query(self) -> Any:
        """Return the base SELECT statement with filters applied."""
        return select(CandidateSpendingTotals)

    def _apply_sorting(
        self,
        stmt: Any,
        sort_by: SpendingSortBy,
        order: Literal["asc", "desc"],
    ) -> Any:
        """Apply sort column and direction with composite PK tiebreaker."""
        sort_options = {
            "cycle": CandidateSpendingTotals.cycle,
            "inside_receipts": CandidateSpendingTotals.inside_receipts,
            "inside_disbursements": CandidateSpendingTotals.inside_disbursements,
            "outside_support": CandidateSpendingTotals.outside_support,
            "outside_oppose": CandidateSpendingTotals.outside_oppose,
            "outside_total": CandidateSpendingTotals.outside_support
            + CandidateSpendingTotals.outside_oppose,
            "influence_ratio": CandidateSpendingTotals.influence_ratio,
            "vulnerability_factor": CandidateSpendingTotals.vulnerability_factor,
        }
        sort_column = sort_options[sort_by]
        direction = desc if order == "desc" else asc
        return stmt.order_by(
            direction(sort_column),
            CandidateSpendingTotals.candidate_id,
            CandidateSpendingTotals.cycle,
        )

    async def get_list(
        self,
        limit: int = 100,
        offset: int = 0,
        sort_by: SpendingSortBy = "outside_total",
        order: Literal["asc", "desc"] = "desc",
    ) -> dict[str, Any]:
        """Return a paginated, sorted list of candidate spending totals."""
        base_stmt = self._build_base_query()

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_count = (await self.db.execute(count_stmt)).scalar() or 0

        data_stmt = base_stmt.options(joinedload(CandidateSpendingTotals.candidate))
        data_stmt = (
            self._apply_sorting(data_stmt, sort_by, order).limit(limit).offset(offset)
        )
        result = await self.db.execute(data_stmt)

        return {
            "items": result.scalars().all(),
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }
