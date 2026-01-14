from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, func

from civic_lantern.db.models.base import Base


class TotalsByElection(Base):
    __tablename__ = "totals_by_election"
    __table_args__ = (Index("idx_totals_by_election_election_id", "election_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    election_id = Column(Integer, ForeignKey("elections.election_id"))

    disbursements = Column(Numeric(14, 2), nullable=False, server_default="0")
    independent_expenditures = Column(
        Numeric(14, 2), nullable=False, server_default="0"
    )
    receipts = Column(Numeric(14, 2), nullable=False, server_default="0")

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
