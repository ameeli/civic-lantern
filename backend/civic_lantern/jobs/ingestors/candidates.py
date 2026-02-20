from typing import Any, Dict, List

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.services.data.candidate import CandidateService
from civic_lantern.utils.transformers import transform_candidates


class CandidateIngestor(BaseIngestor):
    """Ingests candidate data from the FEC API."""

    entity_name = "candidates"

    async def fetch(
        self, start_date: str, end_date: str, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Fetch candidates from FEC API."""
        return await self.client.get_candidates(
            min_first_file_date=start_date,
            max_first_file_date=end_date,
            **kwargs,
        )

    def transform(self, raw_data: List[Dict[str, Any]]) -> list:
        """Validate raw candidate dicts through CandidateIn schema."""
        return transform_candidates(raw_data)

    def create_service(self) -> CandidateService:
        """Return a CandidateService wired to the current DB session."""
        return CandidateService(db=self.session)
