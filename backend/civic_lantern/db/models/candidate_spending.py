from sqlalchemy import Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from civic_lantern.db.models.base import Base
from civic_lantern.db.models.mixins import TimestampMixin


class CandidateSpendingTotals(Base, TimestampMixin):
    __tablename__ = "candidate_spending_totals"

    # Composite Primary Key
    candidate_id = Column(
        String, ForeignKey("candidates.candidate_id"), primary_key=True
    )
    cycle = Column(Integer, primary_key=True)

    inside_receipts = Column(Numeric(15, 2), default=0.0)
    inside_disbursements = Column(Numeric(15, 2), default=0.0)

    outside_support = Column(Numeric(15, 2), default=0.0)
    outside_oppose = Column(Numeric(15, 2), default=0.0)

    influence_ratio = Column(Numeric(10, 2), default=0.0)
    vulnerability_factor = Column(Numeric(10, 2), default=0.0)

    candidate = relationship("Candidate", back_populates="spending_totals")

    def __repr__(self):
        return (
            f"<CandidateSpendingTotals(id='{self.candidate_id}', "
            f"cycle={self.cycle}, ratio={self.influence_ratio})>"
        )
