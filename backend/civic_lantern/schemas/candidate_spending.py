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
    inside_receipts: Optional[float] = None
    inside_disbursements: Optional[float] = None
    outside_support: Optional[float] = None
    outside_oppose: Optional[float] = None
    influence_ratio: Optional[float] = None
    vulnerability_factor: Optional[float] = None
    candidate: Optional[CandidateInfo] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _compute_ratios(self) -> "CandidateSpendingSchema":
        """Compute influence_ratio and vulnerability_factor from spending data."""
        denom = self.inside_disbursements
        if not denom:
            self.influence_ratio = None
            self.vulnerability_factor = None
            return self
        support = self.outside_support or 0.0
        oppose = self.outside_oppose or 0.0
        self.influence_ratio = round((support + oppose) / denom, 2)
        self.vulnerability_factor = round(oppose / denom, 2)
        return self


class CandidateSpendingList(BaseModel):
    items: list[CandidateSpendingSchema]
    total_count: int
    limit: int
    offset: int
