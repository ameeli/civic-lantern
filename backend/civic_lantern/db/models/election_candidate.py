from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)

from civic_lantern.db.models.base import Base


class ElectionCandidate(Base):
    __tablename__ = "election_candidates"
    __table_args__ = (
        Index("idx_election_candidates_candidate_id", "candidate_id"),
        UniqueConstraint("election_id", "candidate_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    election_id = Column(Integer, ForeignKey("elections.election_id"))
    candidate_id = Column(String, ForeignKey("candidates.candidate_id"))

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
