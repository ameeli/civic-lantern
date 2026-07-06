from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class InsideTotalsByCandidateIn(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    cycle: int
    receipts: Optional[float] = None
    disbursements: Optional[float] = None

    model_config = ConfigDict(str_strip_whitespace=True)
