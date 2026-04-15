from typing import Optional

from pydantic import BaseModel, ConfigDict


class ElectionSpending(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cycle: int
    candidate_count: int
    total_inside_receipts: Optional[float]
    total_inside_disbursements: Optional[float]
    total_outside_support: Optional[float]
    total_outside_oppose: Optional[float]
    global_influence_ratio: Optional[float]
