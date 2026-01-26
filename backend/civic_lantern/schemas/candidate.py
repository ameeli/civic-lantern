from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from civic_lantern.db.models.enums import OfficeTypeEnum


class CandidateIn(BaseModel):
    candidate_id: str = Field(
        description="Unique FEC candidate ID", pattern=r"^[CHP]\d{8}$"
    )
    name: Optional[str] = None
    office: Optional[OfficeTypeEnum] = None
    state: Optional[str] = None
    party: Optional[str]
    party_full: Optional[str]
    district: Optional[str]
    incumbent_challenge: Optional[str]
    incumbent_challenge_full: Optional[str]
    candidate_status: Optional[str]
    active_through: Optional[int]
    cycles: List[int] = Field(default_factory=list)
    election_years: List[int] = Field(default_factory=list)
    federal_funds_flag: Optional[bool]
    has_raised_funds: Optional[bool]
    first_file_date: Optional[date]
    last_f2_date: Optional[date]
    last_file_date: Optional[date]
    load_date: Optional[datetime]

    model_config = {
        "extra": "ignore",  # Ignore extra fields from FEC API
        "str_strip_whitespace": True,
    }

    @field_validator("office", mode="before")
    @classmethod
    def normalize_office(cls, v):
        if isinstance(v, str):
            return v.upper()
        return v
