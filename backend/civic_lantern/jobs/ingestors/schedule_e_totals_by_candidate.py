from typing import Any, Dict, List

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.services.data.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidateService,
)
from civic_lantern.services.fec_client import FEDERAL_OFFICES, FECEndpoint
from civic_lantern.utils.transformers import transform_schedule_e_totals_by_candidate

SCHEDULE_E_TOTALS = FECEndpoint(
    name="schedule E totals by candidate",
    path="/schedules/schedule_e/totals/by_candidate/",
    # Rows are unique per (candidate_id, support_oppose_indicator) in a cycle.
    sort=("candidate_id", "support_oppose_indicator"),
    params={"office": FEDERAL_OFFICES},
    required=("cycle",),
)


class ScheduleETotalsByCandidateIngestor(BaseIngestor):
    """Ingests outside spending totals from the FEC schedule_e totals-by-candidate
    feed."""

    entity_name = "schedule_e_totals_by_candidate"

    # Narrower than the base **kwargs; IngestionManager always passes `cycle`.
    async def fetch(  # type: ignore[override]
        self, cycle: int, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Fetch IE totals per candidate for the given cycle."""
        return await self.client.fetch_all(SCHEDULE_E_TOTALS, cycle=cycle, **kwargs)

    def transform(self, raw_data: List[Dict[str, Any]]) -> list:
        """Validate raw schedule E totals."""
        return transform_schedule_e_totals_by_candidate(raw_data)

    def create_service(self) -> ScheduleETotalsByCandidateService:
        """Return ScheduleETotalsByCandidateService wired to the current DB session."""
        return ScheduleETotalsByCandidateService(db=self.session)
