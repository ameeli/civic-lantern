from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.inside_totals_by_candidate import InsideTotalsByCandidate
from civic_lantern.services.data.base import BaseService


class InsideTotalsByCandidateService(BaseService[InsideTotalsByCandidate]):
    index_elements = ["candidate_id", "cycle"]

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(model=InsideTotalsByCandidate, db=db)
