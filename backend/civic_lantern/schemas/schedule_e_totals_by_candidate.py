from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from civic_lantern.db.models.enums import SupportOpposeEnum


class ScheduleETotalsByCandidateIn(BaseModel):
    committee_id: str = Field(..., min_length=1)
    candidate_id: str = Field(..., min_length=1)
    cycle: int
    support_oppose_indicator: SupportOpposeEnum
    total: Optional[float] = None
    count: Optional[int] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("support_oppose_indicator", mode="before")
    @classmethod
    def normalize_indicator(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v
