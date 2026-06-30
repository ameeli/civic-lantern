from sqlalchemy import Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from civic_lantern.db.models.base import Base
from civic_lantern.db.models.mixins import TimestampMixin


class CandidateInsideTotals(Base, TimestampMixin):
    __tablename__ = "candidate_inside_totals"

    candidate_id = Column(
        String, ForeignKey("candidates.candidate_id"), primary_key=True
    )
    cycle = Column(Integer, primary_key=True)

    receipts = Column(Numeric(15, 2))
    disbursements = Column(Numeric(15, 2))

    candidate = relationship("Candidate")

    def __repr__(self) -> str:
        return (
            f"<CandidateInsideTotals(candidate_id='{self.candidate_id}', "
            f"cycle={self.cycle}, disbursements={self.disbursements})>"
        )
