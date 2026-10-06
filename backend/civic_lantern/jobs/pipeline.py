"""One pipeline that ingests any FEC entity from its Ingestion declaration.

Steps: resolve the scope, fetch, apply corrections, validate, combine rows that
share a primary key, upsert, and record the run in `ingestion_runs`.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Type, Union
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ValidationError
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.ingestion_run import IngestionRunStatus
from civic_lantern.services.committee_corrections import CommitteeCorrections
from civic_lantern.services.data.base import BaseService, UpsertStats
from civic_lantern.services.data.ingestion_run import IngestionRunService
from civic_lantern.services.fec_client import FECClient, FECEndpoint
from civic_lantern.services.fec_exceptions import PartialFetchError

logger = logging.getLogger(__name__)

# FEC operates on the US/Eastern filing calendar
FEC_TIMEZONE = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class DateWindow:
    """Resume from the watermark; the window is sent as these FEC filter params."""

    min_param: str
    max_param: str


@dataclass(frozen=True)
class PerCycle:
    """Re-pull one election cycle on every run."""


Scope = Union[DateWindow, PerCycle]


class InvalidRowError(ValueError):
    """A row of a summing ingestion failed validation; skipping it would
    understate that key's total, so the run fails instead."""


@dataclass(frozen=True, eq=False)
class Ingestion:
    """The declaration of one FEC entity, run by run_ingestion()."""

    entity: str
    scope: Scope
    endpoint: FECEndpoint
    schema: Type[BaseModel]
    model: Type[Any]
    corrections: Optional[CommitteeCorrections] = None
    # Fields summed across rows that share a primary key; others keep the first row.
    sum_duplicates: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        fields = set(self.schema.model_fields)
        missing = [
            k for k in (*self.key_columns, *self.sum_duplicates) if k not in fields
        ]
        if missing:
            raise ValueError(f"{self.entity}: {missing} not on {self.schema.__name__}")
        if set(self.sum_duplicates) & set(self.key_columns):
            raise ValueError(f"{self.entity}: can't sum primary key columns")
        if self.corrections and not isinstance(self.scope, PerCycle):
            raise ValueError(f"{self.entity}: corrections need a per-cycle scope")

    @property
    def key_columns(self) -> Tuple[str, ...]:
        return tuple(col.name for col in inspect(self.model).primary_key)

    @property
    def per_cycle(self) -> bool:
        return isinstance(self.scope, PerCycle)

    @property
    def accepts_partial_fetch(self) -> bool:
        """Partial rows are safe only when no row is built from several pieces."""
        return self.corrections is None and not self.sum_duplicates


async def run_ingestion(
    ingestion: Ingestion,
    client: FECClient,
    session: AsyncSession,
    *,
    cycle: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[UpsertStats]:
    """Fetch → validate → combine → upsert, tracked in `ingestion_runs` by
    (entity, cycle). Dates are ignored for per-cycle ingestions."""
    if ingestion.per_cycle and cycle is None:
        raise ValueError(f"{ingestion.entity} runs per cycle; pass a cycle")
    if not ingestion.per_cycle and cycle is not None:
        raise ValueError(f"{ingestion.entity} uses a date window, not a cycle")

    logger.info(f"Syncing {ingestion.entity}")
    run_tracker = IngestionRunService(session)
    run_row = await run_tracker.start_run(ingestion.entity, cycle)

    partial_note = None
    try:
        try:
            raw_data = await _fetch(
                ingestion, client, session, cycle, start_date, end_date
            )
        except PartialFetchError as e:
            if not ingestion.accepts_partial_fetch:
                raise
            # Keep the pages that loaded, but as PARTIAL_SUCCESS so the
            # watermark doesn't skip past what the failed pages held.
            logger.warning(
                f"{ingestion.entity}: {e}; "
                f"ingesting {len(e.results)} records fetched so far"
            )
            raw_data = e.results
            partial_note = str(e)

        rows = combine(validate(raw_data, ingestion), ingestion)

        if not rows:
            logger.info(f"No {ingestion.entity} found to ingest.")
            status = (
                IngestionRunStatus.PARTIAL_SUCCESS
                if partial_note
                else IngestionRunStatus.SUCCESS
            )
            await run_tracker.complete_run(
                run_row, status=status, error_message=partial_note
            )
            return None

        stats = await BaseService(ingestion.model, db=session).upsert_batch(rows)
        logger.info(
            f"{ingestion.entity} complete: "
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
        logger.warning(f"{ingestion.entity} ingestion cancelled")
        await session.rollback()
        await run_tracker.complete_run(
            run_row,
            status=IngestionRunStatus.CANCELLED,
            error_message="Run was cancelled",
        )
        raise
    except Exception as e:
        logger.error(f"{ingestion.entity} ingestion failed: {e}", exc_info=True)
        # Roll back first: an aborted transaction would make complete_run's
        # commit raise too, masking this error and leaving the row IN_PROGRESS.
        await session.rollback()
        await run_tracker.complete_run(
            run_row, status=IngestionRunStatus.FAILED, error_message=str(e)
        )
        raise


async def _fetch(
    ingestion: Ingestion,
    client: FECClient,
    session: AsyncSession,
    cycle: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
) -> List[Dict[str, Any]]:
    params: Dict[str, Any]
    if isinstance(ingestion.scope, DateWindow):
        params = await _date_window_params(
            ingestion, ingestion.scope, session, start_date, end_date
        )
    else:
        params = {"cycle": cycle}
    rows = await client.fetch_all(ingestion.endpoint, **params)
    if ingestion.corrections is not None:
        assert cycle is not None  # corrections require a per-cycle scope
        inputs = await ingestion.corrections.fetch_inputs(client, cycle)
        rows = ingestion.corrections.apply(rows, cycle, inputs)
    return rows


async def _date_window_params(
    ingestion: Ingestion,
    scope: DateWindow,
    session: AsyncSession,
    start_date: Optional[str],
    end_date: Optional[str],
) -> Dict[str, Any]:
    """Resume from the last successful run's watermark (US/Eastern). With no
    prior run there's no lower bound: a full pull, so later FK lookups succeed."""
    if not end_date:
        end_date = datetime.now(FEC_TIMEZONE).strftime("%Y-%m-%d")
    if not start_date:
        watermark = await IngestionRunService(session).get_watermark(ingestion.entity)
        # Don't hold the connection through a possibly hours-long fetch.
        await session.commit()
        if watermark:
            start_date = watermark.astimezone(FEC_TIMEZONE).strftime("%Y-%m-%d")

    params: Dict[str, Any] = {scope.max_param: end_date}
    if start_date:
        params[scope.min_param] = start_date
    return params


def validate(raw_rows: List[Dict[str, Any]], ingestion: Ingestion) -> List[BaseModel]:
    """Validate rows through the schema, skipping invalid ones. For a summing
    ingestion, an invalid row that has its key raises InvalidRowError."""
    valid: List[BaseModel] = []
    for idx, raw in enumerate(raw_rows):
        key = tuple(raw.get(k) for k in ingestion.key_columns)
        try:
            valid.append(ingestion.schema.model_validate(raw))
        except ValidationError as e:
            if ingestion.sum_duplicates and all(key):
                raise InvalidRowError(
                    f"{ingestion.entity} {key} failed validation: {_first_error(e)}"
                ) from e
            logger.warning(f"Skipping {ingestion.entity} {key}: {_first_error(e)}")
        except Exception as e:
            if ingestion.sum_duplicates:
                raise
            logger.error(f"Unexpected crash on {ingestion.entity} {key}: {e}")
    logger.info(f"Validated {len(valid)}/{len(raw_rows)} {ingestion.entity} records.")
    return valid


def combine(rows: List[BaseModel], ingestion: Ingestion) -> List[BaseModel]:
    """Merge rows that share a primary key, in first-seen order: sum the
    sum_duplicates fields (None counts as 0), otherwise keep the first row."""
    groups: Dict[tuple, List[BaseModel]] = {}
    for row in rows:
        key = tuple(getattr(row, k) for k in ingestion.key_columns)
        groups.setdefault(key, []).append(row)

    if not ingestion.sum_duplicates:
        duplicates = [key for key, group in groups.items() if len(group) > 1]
        if duplicates:
            logger.warning(
                f"{ingestion.entity}: {len(duplicates)} duplicate key(s); kept the "
                f"first row of each. Examples: {duplicates[:5]}"
            )
        return [group[0] for group in groups.values()]

    combined = []
    for group in groups.values():
        totals = {}
        for name in ingestion.sum_duplicates:
            total = 0.0
            for row in group:
                total += getattr(row, name) or 0.0
            totals[name] = total
        combined.append(group[0].model_copy(update=totals))
    return combined


def _first_error(e: ValidationError) -> str:
    err = e.errors()[0]
    location = ".".join(str(part) for part in err["loc"])
    return f"{location}: {err['msg']}"
