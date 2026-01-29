from civic_lantern.db.models.candidate import Candidate
from civic_lantern.services.data.base import BaseService


class CandidateService(BaseService[Candidate]):
    def __init__(self, db):
        super().__init__(model=Candidate, db=db)
