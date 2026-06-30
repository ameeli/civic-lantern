from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.candidate_inside_totals import CandidateInsideTotals
from civic_lantern.services.data.base import BaseService


class CandidateInsideTotalsService(BaseService[CandidateInsideTotals]):
    index_elements = ["candidate_id", "cycle"]

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(model=CandidateInsideTotals, db=db)
