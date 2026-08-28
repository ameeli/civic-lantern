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

        Pass start_date/end_date to filter by first file date explicitly.
        Omitting either resumes from the last successful run's watermark, or
        does a full unfiltered pull on the very first run (no watermark yet).
        Pass election_year to filter by cycle.
        """
        start_date, end_date = await self._resolve_dates(start_date, end_date)
        if start_date:
            kwargs["min_first_file_date"] = start_date
        kwargs["max_first_file_date"] = end_date
        return await self.client.get_candidates(**kwargs)

    def transform(self, raw_data: List[Dict[str, Any]]) -> list:
        """Validate raw candidate dicts through CandidateIn schema."""
        return transform_candidates(raw_data)

    def create_service(self) -> CandidateService:
        """Return a CandidateService wired to the current DB session."""
        return CandidateService(db=self.session)
