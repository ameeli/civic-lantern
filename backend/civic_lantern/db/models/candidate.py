from sqlalchemy import (
    ARRAY,
    CHAR,
    Boolean,
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    String,
)
from sqlalchemy import Enum as SQLEnum

from civic_lantern.db.models.base import Base, enum_values_callable
from civic_lantern.db.models.enums import OfficeTypeEnum
from civic_lantern.db.models.mixins import TimestampMixin


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidates"
    __table_args__ = (
        Index("idx_candidates_state_office", "state", "office"),
        Index("idx_candidates_cycles", "cycles", postgresql_using="gin"),
    )

    candidate_id = Column(String, primary_key=True, nullable=False)
    name = Column(String, nullable=False)

    office = Column(
        SQLEnum(
            OfficeTypeEnum,
            name="office_enum",
            values_callable=enum_values_callable,
        ),
        nullable=False,
    )

    party = Column(String)
    party_full = Column(String)

    state = Column(CHAR(2), nullable=False)
    district = Column(CHAR(2))

    incumbent_challenge = Column(CHAR(1))
    incumbent_challenge_full = Column(String)

    candidate_status = Column(CHAR(1))
    active_through = Column(Integer)

    cycles = Column(ARRAY(Integer))
    election_years = Column(ARRAY(Integer))

    federal_funds_flag = Column(Boolean)
    has_raised_funds = Column(Boolean)

    first_file_date = Column(Date)
    last_f2_date = Column(Date)
    last_file_date = Column(Date)
    load_date = Column(DateTime(timezone=True))
