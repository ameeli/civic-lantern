from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy import Enum as SQLEnum

from civic_lantern.db.models.base import Base, enum_values_callable
from civic_lantern.db.models.enums import SupportOpposeEnum
from civic_lantern.db.models.mixins import TimestampMixin


class ScheduleE(Base, TimestampMixin):
    __tablename__ = "schedule_e"
    __table_args__ = (
        Index("idx_schedule_e_candidate_id", "candidate_id"),
        Index("idx_schedule_e_committee_id", "committee_id"),
    )

    sub_id = Column(String, primary_key=True)

    link_id = Column(BigInteger)
    file_number = Column(Integer)
    previous_file_number = Column(Integer)

    candidate_id = Column(String, ForeignKey("candidates.candidate_id"))
    committee_id = Column(String, ForeignKey("committees.committee_id"))

    support_oppose_indicator = Column(
        SQLEnum(
            SupportOpposeEnum,
            name="support_oppose_enum",
            values_callable=enum_values_callable,
        )
    )
    expenditure_amount = Column(Numeric(14, 2), nullable=False, server_default="0")

    expenditure_date = Column(Date)
    filing_date = Column(Date)

    report_year = Column(Integer)
    report_type = Column(String)

    payee_name = Column(String)
    expenditure_description = Column(String)
