import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.ingestion_run import IngestionRunStatus
from civic_lantern.services.data.base import BaseService
from civic_lantern.services.data.ingestion_run import IngestionRunService
from civic_lantern.services.fec_client import FECClient
from civic_lantern.services.fec_exceptions import PartialFetchError

# FEC operates on the US/Eastern filing calendar
FEC_TIMEZONE = ZoneInfo("America/New_York")


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
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """Execute the ingestion pipeline: fetch → transform → upsert.

        Tracks the attempt in `ingestion_runs`, keyed by (entity_name, cycle).
        `cycle` is None for date-windowed ingestors (candidates, committees)
        and an int for the two cycle-scoped spending ingestors.
        """
        self.logger.info(f"Syncing {self.entity_name}")

        cycle = kwargs.get("cycle")
        if cycle is not None:
            # Cycle-scoped ingestors take no date window — run_nightly()
            # invokes them through the same ingest_batch() path used by
            # date-windowed ingestors, which always forwards start_date/
            # end_date (usually None). Stripping here once means individual
            # cycle-scoped ingestors don't each need to repeat this.
            kwargs.pop("start_date", None)
            kwargs.pop("end_date", None)

        run_tracker = IngestionRunService(self.session)
        run_row = await run_tracker.start_run(self.entity_name, cycle)

        partial_note = None
        try:
            try:
                raw_data = await self.fetch(**kwargs)
            except PartialFetchError as e:
                # Some pages failed even after retries. Don't discard the
                # pages that did succeed — but the run can't be a clean
                # SUCCESS, since resuming from a watermark set now would
                # permanently skip whatever those pages held.
                self.logger.warning(
                    f"{self.entity_name}: {e}; "
                    f"ingesting {len(e.results)} records fetched so far"
                )
                raw_data = e.results
                partial_note = str(e)

            transformed = self.transform(raw_data)

            if not transformed:
                self.logger.info(f"No {self.entity_name} found to ingest.")
                status = (
                    IngestionRunStatus.PARTIAL_SUCCESS
                    if partial_note
                    else IngestionRunStatus.SUCCESS
                )
                await run_tracker.complete_run(
                    run_row, status=status, error_message=partial_note
                )
                return None

            service = self.create_service()
            stats = await service.upsert_batch(transformed)
            self.logger.info(
                f"{self.entity_name} complete: "
                f"{stats['inserted']} inserted, "
                f"{stats['updated']} updated, "
                f"{stats['errors']} errors"
            )

            error_message = partial_note
            if stats["errors"]:
                failed_ids = stats["failed_ids"]
                preview = failed_ids[:20]
                extra = len(failed_ids) - 20
                suffix = f" (+{extra} more)" if extra > 0 else ""
                upsert_note = (
                    f"{stats['errors']} row(s) failed to upsert: {preview}{suffix}"
                )
                error_message = (
                    f"{error_message}; {upsert_note}" if error_message else upsert_note
                )
            status = (
                IngestionRunStatus.PARTIAL_SUCCESS
                if error_message
                else IngestionRunStatus.SUCCESS
            )
            await run_tracker.complete_run(
                run_row, status=status, error_message=error_message
            )
            return stats
        except Exception as e:
            self.logger.error(
                f"{self.entity_name} ingestion failed: {e}", exc_info=True
            )
            # The exception may have left the session's transaction aborted
            # (e.g. a bare commit() failing inside upsert_batch) — roll back
            # first, or complete_run's own commit() would raise too, masking
            # this error and leaving the row stuck IN_PROGRESS.
            await self.session.rollback()
            await run_tracker.complete_run(
                run_row, status=IngestionRunStatus.FAILED, error_message=str(e)
            )
            raise

    @property
    @abstractmethod
    def entity_name(self) -> str:
        """Human-readable name for logging (e.g. 'candidates')."""
        ...

    @abstractmethod
    async def fetch(self, **kwargs: Any) -> List[Dict[str, Any]]:
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

    async def _resolve_dates(
        self, start_date: Optional[str], end_date: Optional[str]
    ) -> tuple[Optional[str], str]:
        """Resume from the last successful run's watermark, in US/Eastern.

        Returns `start_date=None` (no lower bound — a full historical pull)
        when no prior successful run exists yet. A 1-day lookback would leave
        a newly-activated cycle's candidate/committee roster incomplete,
        causing downstream FK violations when spending totals for candidates
        outside that narrow window are ingested. The full pull only happens
        once; every subsequent run resumes from the watermark it sets.
        """
        now_et = datetime.now(FEC_TIMEZONE)
        if not end_date:
            end_date = now_et.strftime("%Y-%m-%d")
        if not start_date:
            watermark = await IngestionRunService(self.session).get_watermark(
                self.entity_name
            )
            start_date = (
                watermark.astimezone(FEC_TIMEZONE).strftime("%Y-%m-%d")
                if watermark
                else None
            )
        return start_date, end_date
