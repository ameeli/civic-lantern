from civic_lantern.db.models.candidate_spending import CandidateSpendingTotals
from civic_lantern.services.data.base import BaseService


class CandidateSpendingService(BaseService[CandidateSpendingTotals]):
    def __init__(self, db):
        super().__init__(model=CandidateSpendingTotals, db=db)

        self.index_elements = ["candidate_id", "cycle"]
