from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidate,
)
from civic_lantern.services.data.base import BaseService


class ScheduleETotalsByCandidateService(BaseService[ScheduleETotalsByCandidate]):
    index_elements = [
        "committee_id",
        "candidate_id",
        "cycle",
        "support_oppose_indicator",
    ]

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(model=ScheduleETotalsByCandidate, db=db)
