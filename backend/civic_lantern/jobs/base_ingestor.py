import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.ingestion_run import IngestionRunStatus
from civic_lantern.services.data.base import BaseService, UpsertStats
from civic_lantern.services.data.ingestion_run import IngestionRunService
from civic_lantern.services.fec_client import FECClient
from civic_lantern.services.fec_exceptions import PartialFetchError

# FEC operates on the US/Eastern filing calendar
FEC_TIMEZONE = ZoneInfo("America/New_York")


class BaseIngestor(ABC):
    """Shared fetch → transform → upsert workflow for FEC ingestion.
    Subclasses supply entity_name, fetch, transform and create_service."""

    # False when fetch() sums several FEC calls per row, so partial rows are wrong.
    accepts_partial_fetch: bool = True

    def __init__(self, client: FECClient, session: AsyncSession):
        self.client = client
        self.session = session
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def run(
        self,
        **kwargs: Any,
    ) -> Optional[UpsertStats]:
        """Fetch → transform → upsert, tracked in `ingestion_runs` by (entity, cycle).
        `cycle` is None for date-windowed ingestors, an int for cycle-scoped ones."""
        self.logger.info(f"Syncing {self.entity_name}")

        cycle = kwargs.get("cycle")
        if cycle is not None:
            # ingest_batch() always forwards dates; cycle-scoped fetch() takes none.
            kwargs.pop("start_date", None)
            kwargs.pop("end_date", None)

        run_tracker = IngestionRunService(self.session)
        run_row = await run_tracker.start_run(self.entity_name, cycle)

        partial_note = None
        try:
            try:
                raw_data = await self.fetch(**kwargs)
            except PartialFetchError as e:
                if not self.accepts_partial_fetch:
                    raise
                # Keep the pages that loaded, but as PARTIAL_SUCCESS so the
                # watermark doesn't skip past what the failed pages held.
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
        except asyncio.CancelledError:
            # SIGTERM arrives as cancellation (see ingestion.py). Record it so the
            # row isn't stuck IN_PROGRESS, then re-raise to honour cancellation.
            self.logger.warning(f"{self.entity_name} ingestion cancelled")
            await self.session.rollback()
            await run_tracker.complete_run(
                run_row,
                status=IngestionRunStatus.CANCELLED,
                error_message="Run was cancelled",
            )
            raise
        except Exception as e:
            self.logger.error(
                f"{self.entity_name} ingestion failed: {e}", exc_info=True
            )
            # Roll back first: an aborted transaction would make complete_run's
            # commit raise too, masking this error and leaving the row IN_PROGRESS.
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
        """Resume from the last successful run's watermark (US/Eastern). With no
        prior run, start_date is None: a full pull, so later FK lookups succeed."""
        now_et = datetime.now(FEC_TIMEZONE)

        if not end_date:
            end_date = now_et.strftime("%Y-%m-%d")
        if not start_date:
            watermark = await IngestionRunService(self.session).get_watermark(
                self.entity_name
            )
            await self.session.commit()

            start_date = (
                watermark.astimezone(FEC_TIMEZONE).strftime("%Y-%m-%d")
                if watermark
                else None
            )
        return start_date, end_date
