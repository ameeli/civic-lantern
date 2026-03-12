from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

SpendingSortBy = Literal[
    "cycle",
    "inside_receipts",
    "inside_disbursements",
    "outside_support",
    "outside_oppose",
    "outside_total",
    "influence_ratio",
    "vulnerability_factor",
]


class CandidateSpendingSchema(BaseModel):
    candidate_id: str
    cycle: int
    inside_receipts: Optional[Decimal] = None
    inside_disbursements: Optional[Decimal] = None
    outside_support: Optional[Decimal] = None
    outside_oppose: Optional[Decimal] = None
    influence_ratio: Optional[Decimal] = None
    vulnerability_factor: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class CandidateSpendingList(BaseModel):
    items: list[CandidateSpendingSchema]
    total_count: int
    limit: int
    offset: int
