from typing import Any, Dict, List

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.services.data.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidateService,
)
from civic_lantern.utils.transformers import transform_schedule_e_totals_by_candidate


class ScheduleETotalsByCandidateIngestor(BaseIngestor):
    """Ingests outside spending totals from /schedules/schedule_e/totals/by_candidate/."""

    entity_name = "schedule_e_totals_by_candidate"

    async def fetch(self, cycle: int = 2024, **kwargs: Any) -> List[Dict[str, Any]]:
        """Fetch IE totals per candidate for the given cycle."""
        kwargs.pop("start_date", None)
        kwargs.pop("end_date", None)
        return await self.client.get_outside_spending_totals(cycle=cycle, **kwargs)

    def transform(self, raw_data: List[Dict[str, Any]]) -> list:
        """Validate raw schedule E totals."""
        return transform_schedule_e_totals_by_candidate(raw_data)

    def create_service(self) -> ScheduleETotalsByCandidateService:
        """Return ScheduleETotalsByCandidateService wired to the current DB session."""
        return ScheduleETotalsByCandidateService(db=self.session)
