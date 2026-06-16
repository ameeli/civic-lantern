from sqlalchemy import CHAR, Column, Date, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY

from civic_lantern.db.models.base import Base, enum_values_callable
from civic_lantern.db.models.enums import CommitteeTypeEnum
from civic_lantern.db.models.mixins import TimestampMixin


class Committee(Base, TimestampMixin):
    __tablename__ = "committees"

    committee_id = Column(String, primary_key=True, nullable=False)
    name = Column(String)
    affiliated_committee_name = Column(String)
    candidate_ids = Column(ARRAY(String))
    sponsor_candidate_ids = Column(ARRAY(String))

    committee_type = Column(
        SQLEnum(
            CommitteeTypeEnum,
            name="committee_type_enum",
            values_callable=enum_values_callable,
        ),
        nullable=False,
    )

    cycles = Column(ARRAY(Integer))
    designation = Column(CHAR(1))
    designation_full = Column(String)
    filing_frequency = Column(CHAR(1))

    first_f1_date = Column(Date)
    first_file_date = Column(Date)
    last_f1_date = Column(Date)
    last_file_date = Column(Date)

    organization_type = Column(CHAR(1))
    organization_type_full = Column(String)
    party = Column(String)
    party_full = Column(String)
    state = Column(CHAR(2))
    treasurer_name = Column(String)

    def __repr__(self) -> str:
        return (
            f"<Committee(id='{self.committee_id}', "
            f"name={self.name!r}, type={self.committee_type})>"
        )
