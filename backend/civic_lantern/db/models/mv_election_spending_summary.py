from sqlalchemy import Column, Integer, Numeric

from civic_lantern.db.models.base import ViewBase


class MvElectionSpendingSummary(ViewBase):
    """Read-only SQLAlchemy model for the mv_election_spending_summary materialized view.

    Inherits from ViewBase (not Base) so it is excluded from Alembic autogenerate
    and integration test create_all/drop_all.
    """

    __tablename__ = "mv_election_spending_summary"

    cycle = Column(Integer, primary_key=True)
    candidate_count = Column(Integer)
    total_inside_receipts = Column(Numeric(15, 2))
    total_inside_disbursements = Column(Numeric(15, 2))
    total_outside_support = Column(Numeric(15, 2))
    total_outside_oppose = Column(Numeric(15, 2))
    global_influence_ratio = Column(Numeric(10, 2))

    def __repr__(self) -> str:
        return (
            f"<MvElectionSpendingSummary(cycle={self.cycle}, "
            f"ratio={self.global_influence_ratio})>"
        )
