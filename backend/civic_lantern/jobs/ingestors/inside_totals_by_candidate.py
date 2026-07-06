from typing import Any, Dict, List

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.services.data.inside_totals_by_candidate import (
    InsideTotalsByCandidateService,
)
from civic_lantern.utils.transformers import transform_inside_totals_by_candidate


class InsideTotalsByCandidateIngestor(BaseIngestor):
    """Ingests candidate inside spending totals from /candidates/totals/."""

    entity_name = "inside_totals_by_candidate"

    async def fetch(self, cycle: int = 2024, **kwargs: Any) -> List[Dict[str, Any]]:
        """Fetch inside spending totals for all candidates in the given cycle."""
        return await self.client.get_candidate_totals(cycle=cycle, **kwargs)

    def transform(self, raw_data: List[Dict[str, Any]]) -> list:
        """Accumulate and validate raw candidate totals through schema."""
        return transform_inside_totals_by_candidate(raw_data)

    def create_service(self) -> InsideTotalsByCandidateService:
        """Return an InsideTotalsByCandidateService wired to the current DB session."""
        return InsideTotalsByCandidateService(db=self.session)
