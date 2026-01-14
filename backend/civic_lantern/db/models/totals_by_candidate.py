from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SQLEnum

from civic_lantern.db.models.base import Base, enum_values_callable
from civic_lantern.db.models.enums import SupportOpposeEnum


class TotalsByCandidate(Base):
    __tablename__ = "totals_by_candidate"
    __table_args__ = (
        UniqueConstraint("candidate_id", "cycle", "support_oppose_indicator"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String, ForeignKey("candidates.candidate_id"))
    cycle = Column(Integer, nullable=False)
    support_oppose_indicator = Column(
        SQLEnum(
            SupportOpposeEnum,
            name="support_oppose_enum",
            values_callable=enum_values_callable,
        )
    )

    total = Column(Numeric(14, 2), nullable=False, server_default="0")

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
