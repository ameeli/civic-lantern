import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.services.data.base import BaseService
from civic_lantern.services.fec_client import FECClient

logger = logging.getLogger(__name__)


class BaseIngestor(ABC):
    """Base class for FEC data ingestion.

    Defines the shared fetch → transform → upsert workflow.
    Subclasses implement entity_name, fetch, transform, and create_service
    to plug in their specific FEC endpoint, Pydantic schema, and DB service.
    """

    def __init__(self, client: FECClient, session: AsyncSession):
        self.client = client
        self.session = session
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def run(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """Execute the ingestion pipeline: fetch → transform → upsert."""
        start_date, end_date = self._resolve_dates(start_date, end_date)
        self.logger.info(f"Syncing {self.entity_name} from {start_date} to {end_date}")

        raw_data = await self.fetch(start_date, end_date, **kwargs)
        transformed = self.transform(raw_data)

        if not transformed:
            self.logger.info(f"No {self.entity_name} found to ingest.")
            return None

        service = self.create_service()
        try:
            stats = await service.upsert_batch(transformed)
            self.logger.info(
                f"{self.entity_name} complete: "
                f"{stats['upserted']} upserted, {stats['errors']} errors"
            )
            return stats
        except Exception as e:
            self.logger.error(
                f"{self.entity_name} ingestion failed: {e}", exc_info=True
            )
            raise

    @property
    @abstractmethod
    def entity_name(self) -> str:
        """Human-readable name for logging (e.g. 'candidates')."""
        ...

    @abstractmethod
    async def fetch(
        self, start_date: str, end_date: str, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Fetch raw data from the FEC API."""
        ...

    @abstractmethod
    def transform(self, raw_data: List[Dict[str, Any]]) -> list:
        """Validate and transform raw data through Pydantic schemas."""
        ...

    @abstractmethod
    def create_service(self) -> BaseService:
        """Return a configured service instance for upserting."""
        ...

    def _resolve_dates(
        self, start_date: Optional[str], end_date: Optional[str]
    ) -> tuple[str, str]:
        """Default to last 7 days if dates not provided."""
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        return start_date, end_date
