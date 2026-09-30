from typing import Any, Dict, List

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.services.committee_corrections import CommitteeCorrections
from civic_lantern.services.data.inside_totals_by_candidate import (
    InsideTotalsByCandidateService,
)
from civic_lantern.services.fec_client import FEDERAL_OFFICES, FECEndpoint
from civic_lantern.utils.transformers import transform_inside_totals_by_candidate

CANDIDATE_TOTALS = FECEndpoint(
    name="candidate totals",
    path="/candidates/totals/",
    sort=("candidate_id",),
    params={"election_full": "false", "office": FEDERAL_OFFICES},
    required=("cycle",),
)


class InsideTotalsByCandidateIngestor(BaseIngestor):
    """Ingests candidate inside spending totals from /candidates/totals/."""

    entity_name = "inside_totals_by_candidate"

    # Rows sum several FEC calls, so a partial fetch would write wrong totals.
    accepts_partial_fetch = False

    corrections = CommitteeCorrections()

    # Narrower than the base **kwargs; IngestionManager always passes `cycle`.
    async def fetch(  # type: ignore[override]
        self, cycle: int, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Fetch inside spending totals for all candidates in the given cycle,
        with committee corrections applied."""
        raw = await self.client.fetch_all(CANDIDATE_TOTALS, cycle=cycle, **kwargs)
        inputs = await self.corrections.fetch_inputs(self.client, cycle)
        return self.corrections.apply(raw, cycle, inputs)

    def transform(self, raw_data: List[Dict[str, Any]]) -> list:
        """Accumulate and validate raw candidate totals through schema."""
        return transform_inside_totals_by_candidate(raw_data)

    def create_service(self) -> InsideTotalsByCandidateService:
        """Return an InsideTotalsByCandidateService wired to the current DB session."""
        return InsideTotalsByCandidateService(db=self.session)
