from sqlalchemy import Column, Integer, Numeric, String

from civic_lantern.db.models.base import ViewBase


class MvCandidateSpendingSummary(ViewBase):
    """Read-only SQLAlchemy model for the mv_candidate_spending_summary materialized view.

    Inherits from ViewBase (not Base) so it is excluded from Alembic autogenerate
    and integration test create_all/drop_all.

    Sources: inside_totals_by_candidate + schedule_e_totals_by_candidate.
    """

    __tablename__ = "mv_candidate_spending_summary"

    candidate_id = Column(String, primary_key=True)
    cycle = Column(Integer, primary_key=True)

    inside_receipts = Column(Numeric(15, 2))
    inside_disbursements = Column(Numeric(15, 2))
    outside_support = Column(Numeric(15, 2))
    outside_oppose = Column(Numeric(15, 2))
    influence_ratio = Column(Numeric(10, 2))
    vulnerability_factor = Column(Numeric(10, 2))

    def __repr__(self) -> str:
        return (
            f"<MvCandidateSpendingSummary(candidate_id='{self.candidate_id}', "
            f"cycle={self.cycle}, ratio={self.influence_ratio})>"
        )
