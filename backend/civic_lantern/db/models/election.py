from sqlalchemy import CHAR, Column, DateTime, Integer, UniqueConstraint, func
from sqlalchemy import Enum as SQLEnum

from civic_lantern.db.models.base import Base, enum_values_callable
from civic_lantern.db.models.enums import OfficeTypeEnum


class Election(Base):
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
    state = Column(CHAR(2), nullable=False)
    district = Column(CHAR(2))

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
