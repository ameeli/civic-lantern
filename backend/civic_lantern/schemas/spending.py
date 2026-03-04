from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field


class CandidateSpendingSchema(BaseModel):
    candidate_id: str
    cycle: int
    inside_receipts: Optional[Decimal] = None
    inside_disbursements: Optional[Decimal] = None
    outside_support: Optional[Decimal] = None
    outside_oppose: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def influence_ratio(self) -> Decimal:
        disbursements = self.inside_disbursements or Decimal("0")
        support = self.outside_support or Decimal("0")
        oppose = self.outside_oppose or Decimal("0")
        if disbursements > 0:
            return round((support + oppose) / disbursements, 2)
        return Decimal("0.00")

    @computed_field
    @property
    def vulnerability_factor(self) -> Decimal:
        disbursements = self.inside_disbursements or Decimal("0")
        oppose = self.outside_oppose or Decimal("0")
        if disbursements > 0:
            return round(oppose / disbursements, 2)
        return Decimal("0.00")
