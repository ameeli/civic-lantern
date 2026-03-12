from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

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


class CandidateInfo(BaseModel):
    candidate_id: str
    name: Optional[str] = None
    state: Optional[str] = None
    office: Optional[str] = None
    district: Optional[str] = None
    party: Optional[str] = None
    incumbent_challenge: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CandidateSpendingSchema(BaseModel):
    candidate_id: str
    cycle: int
    inside_receipts: Optional[Decimal] = None
    inside_disbursements: Optional[Decimal] = None
    outside_support: Optional[Decimal] = None
    outside_oppose: Optional[Decimal] = None
    influence_ratio: Optional[Decimal] = None
    vulnerability_factor: Optional[Decimal] = None
    candidate: Optional[CandidateInfo] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='after')
    def _compute_ratios(self) -> 'CandidateSpendingSchema':
        """Compute influence_ratio and vulnerability_factor from spending data."""
        denom = self.inside_disbursements
        if not denom:
            self.influence_ratio = None
            self.vulnerability_factor = None
            return self
        support = self.outside_support or Decimal(0)
        oppose = self.outside_oppose or Decimal(0)
        two_dp = Decimal("0.01")
        self.influence_ratio = ((support + oppose) / denom).quantize(two_dp, rounding=ROUND_HALF_UP)
        self.vulnerability_factor = (oppose / denom).quantize(two_dp, rounding=ROUND_HALF_UP)
        return self


class CandidateSpendingList(BaseModel):
    items: list[CandidateSpendingSchema]
    total_count: int
    limit: int
    offset: int
