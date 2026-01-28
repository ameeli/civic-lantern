from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from civic_lantern.db.models.base import Base
from civic_lantern.db.models.mixins import TimestampMixin


class ElectionCandidate(Base, TimestampMixin):
    __tablename__ = "election_candidates"
    __table_args__ = (
        Index("idx_election_candidates_candidate_id", "candidate_id"),
        UniqueConstraint("election_id", "candidate_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    election_id = Column(Integer, ForeignKey("elections.election_id"))
    candidate_id = Column(String, ForeignKey("candidates.candidate_id"))
