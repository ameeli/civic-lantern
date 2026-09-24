from typing import Any, Dict, List

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.services.data.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidateService,
)
from civic_lantern.utils.transformers import transform_schedule_e_totals_by_candidate


class ScheduleETotalsByCandidateIngestor(BaseIngestor):
    """Ingests outside spending totals from the FEC schedule_e totals-by-candidate
    feed."""

    entity_name = "schedule_e_totals_by_candidate"

    # IngestionManager always threads a matching `cycle` kwarg for this
    # cycle-scoped ingestor, so narrowing the base class's fully-generic
    # **kwargs signature is safe in practice.
    async def fetch(  # type: ignore[override]
        self, cycle: int, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Fetch IE totals per candidate for the given cycle."""
        return await self.client.get_candidate_schedule_e_totals(cycle=cycle, **kwargs)

    def transform(self, raw_data: List[Dict[str, Any]]) -> list:
        """Validate raw schedule E totals."""
        return transform_schedule_e_totals_by_candidate(raw_data)

    def create_service(self) -> ScheduleETotalsByCandidateService:
        """Return ScheduleETotalsByCandidateService wired to the current DB session."""
        return ScheduleETotalsByCandidateService(db=self.session)
