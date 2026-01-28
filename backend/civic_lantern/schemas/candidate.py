from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from civic_lantern.db.models.enums import OfficeTypeEnum


class CandidateIn(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
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

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        if isinstance(v, str) and "," in v:
            # Handle potential multiple commas (e.g., "SMITH, JOHN, JR")
            parts = [p.strip() for p in v.split(",")]
            if len(parts) >= 2:
                flipped = f"{parts[1]} {parts[0]}"
                if len(parts) > 2:
                    flipped += f" {parts[2]}"
                v = flipped
        return v.title() if isinstance(v, str) else v

    @field_validator("office", mode="before")
    @classmethod
    def normalize_office(cls, v):
        if isinstance(v, str):
            return v.upper()
        return v

    @field_validator("district")
    @classmethod
    def pad_district(cls, v: Optional[str]) -> Optional[str]:
        """Ensures district '9' becomes '09'."""
        if v and v.isdigit():
            return v.zfill(2)
        return v
