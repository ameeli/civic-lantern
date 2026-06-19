from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from civic_lantern.db.models.enums import CommitteeTypeEnum


class CommitteeIn(BaseModel):
    committee_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    committee_type: CommitteeTypeEnum
    committee_type_full: Optional[str] = None

    affiliated_committee_name: Optional[str] = None
    candidate_ids: list[str] = Field(default_factory=list)
    sponsor_candidate_ids: list[str] = Field(default_factory=list)
    cycles: list[int] = Field(default_factory=list)

    designation: Optional[str] = None
    designation_full: Optional[str] = None
    filing_frequency: Optional[str] = None

    first_f1_date: Optional[date] = None
    first_file_date: Optional[date] = None
    last_f1_date: Optional[date] = None
    last_file_date: Optional[date] = None

    organization_type: Optional[str] = None
    organization_type_full: Optional[str] = None
    party: Optional[str] = None
    party_full: Optional[str] = None
    state: Optional[str] = None
    treasurer_name: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("committee_type", mode="before")
    @classmethod
    def normalize_committee_type(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v

    @field_validator("affiliated_committee_name", mode="before")
    @classmethod
    def normalize_affiliated_committee_name(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip().upper() == "NONE":
            return None
        return v
