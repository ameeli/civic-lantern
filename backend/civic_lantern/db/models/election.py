from sqlalchemy import CHAR, Column, Integer, UniqueConstraint
from sqlalchemy import Enum as SQLEnum

from civic_lantern.db.models.base import Base, enum_values_callable
from civic_lantern.db.models.enums import OfficeTypeEnum
from civic_lantern.db.models.mixins import TimestampMixin


class Election(Base, TimestampMixin):
    __tablename__ = "elections"
    __table_args__ = (UniqueConstraint("cycle", "office", "state", "district"),)

    election_id = Column(Integer, primary_key=True, autoincrement=True)
    cycle = Column(Integer, nullable=False)
    office = Column(
        SQLEnum(
            OfficeTypeEnum,
            name="office_enum",
            values_callable=enum_values_callable,
        ),
        nullable=False,
    )
    state = Column(CHAR(2))
    district = Column(CHAR(2))
