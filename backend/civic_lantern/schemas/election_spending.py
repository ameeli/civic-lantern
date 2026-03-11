from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ElectionSpending(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cycle: int
    candidate_count: int
    total_inside_receipts: Optional[Decimal]
    total_inside_disbursements: Optional[Decimal]
    total_outside_support: Optional[Decimal]
    total_outside_oppose: Optional[Decimal]
    global_influence_ratio: Optional[Decimal]
