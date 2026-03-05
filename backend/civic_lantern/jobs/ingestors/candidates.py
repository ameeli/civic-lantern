from typing import Any, Dict, List, Optional

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.services.data.candidate import CandidateService
from civic_lantern.utils.transformers import transform_candidates


class CandidateIngestor(BaseIngestor):
    """Ingests candidate data from the FEC API."""

    entity_name = "candidates"

    async def fetch(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Fetch candidates from FEC API.

        Pass start_date/end_date to filter by first file date.
        Pass election_year to filter by cycle. Omitting all returns unfiltered results.
        """
        if start_date or end_date:
            start_date, end_date = self._resolve_dates(start_date, end_date)
            kwargs["min_first_file_date"] = start_date
            kwargs["max_first_file_date"] = end_date
        return await self.client.get_candidates(**kwargs)

    def transform(self, raw_data: List[Dict[str, Any]]) -> list:
        """Validate raw candidate dicts through CandidateIn schema."""
        return transform_candidates(raw_data)

    def create_service(self) -> CandidateService:
        """Return a CandidateService wired to the current DB session."""
        return CandidateService(db=self.session)
