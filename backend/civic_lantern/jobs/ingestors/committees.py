from typing import Any, Dict, List, Optional

from civic_lantern.jobs.base_ingestor import BaseIngestor
from civic_lantern.services.data.committee import CommitteeService
from civic_lantern.utils.transformers import transform_committees


class CommitteeIngestor(BaseIngestor):
    """Ingests committee data from the FEC API."""

    entity_name = "committees"

    async def fetch(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Fetch committees from FEC API.

        Pass start_date/end_date to filter by first file date.
        Omitting both returns all committees.
        """
        if start_date or end_date:
            start_date, end_date = self._resolve_dates(start_date, end_date)
            kwargs["min_first_file_date"] = start_date
            kwargs["max_first_file_date"] = end_date
        return await self.client.get_committees(**kwargs)

    def transform(self, raw_data: List[Dict[str, Any]]) -> list:
        """Validate raw committee dicts through CommitteeIn schema."""
        return transform_committees(raw_data)

    def create_service(self) -> CommitteeService:
        """Return a CommitteeService wired to the current DB session."""
        return CommitteeService(db=self.session)
