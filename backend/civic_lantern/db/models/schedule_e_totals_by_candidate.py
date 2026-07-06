from sqlalchemy import Column, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from civic_lantern.db.models.base import Base, enum_values_callable
from civic_lantern.db.models.enums import SupportOpposeEnum
from civic_lantern.db.models.mixins import TimestampMixin


class ScheduleETotalsByCandidate(Base, TimestampMixin):
    __tablename__ = "schedule_e_totals_by_candidate"

    # No FK on committee_id — some filers may not be in our committees table.
    committee_id = Column(String, primary_key=True)
    candidate_id = Column(
        String, ForeignKey("candidates.candidate_id"), primary_key=True
    )
    cycle = Column(Integer, primary_key=True)
    support_oppose_indicator = Column(
        SQLEnum(
            SupportOpposeEnum,
            name="support_oppose_enum",
            values_callable=enum_values_callable,
            create_type=False,
        ),
        primary_key=True,
    )

    total = Column(Numeric(14, 2))
    count = Column(Integer)

    candidate = relationship("Candidate")

    def __repr__(self) -> str:
        return (
            f"<ScheduleETotalsByCandidate("
            f"committee_id='{self.committee_id}', "
            f"candidate_id='{self.candidate_id}', "
            f"cycle={self.cycle}, "
            f"indicator={self.support_oppose_indicator}, "
            f"total={self.total})>"
        )
