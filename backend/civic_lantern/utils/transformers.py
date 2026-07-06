import logging
from typing import Any, Dict, List, Type, TypeVar

from pydantic import BaseModel, ValidationError

from civic_lantern.schemas.candidate import CandidateIn
from civic_lantern.schemas.committee import CommitteeIn
from civic_lantern.schemas.inside_totals_by_candidate import InsideTotalsByCandidateIn

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _transform_records(
    raw_records: List[Dict[str, Any]],
    schema_cls: Type[T],
    id_field: str,
    entity_name: str,
) -> List[T]:
    transformed = []
    for idx, raw in enumerate(raw_records):
        record_id = raw.get(id_field, f"index {idx}")
        try:
            transformed.append(schema_cls.model_validate(raw))
        except ValidationError as e:
            logger.warning(f"Skipping {entity_name} {record_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected crash on {entity_name} {record_id}: {e}")

    seen: dict[str, T] = {}
    for record in transformed:
        seen[getattr(record, id_field)] = record
    deduped = list(seen.values())

    if len(deduped) < len(transformed):
        logger.warning(
            f"Dropped {len(transformed) - len(deduped)} duplicate {id_field}(s)."
        )

    logger.info(f"Successfully transformed {len(deduped)}/{len(raw_records)} records.")

    return deduped


def transform_candidates(raw_candidates: List[Dict[str, Any]]) -> List[CandidateIn]:
    """Transform raw FEC candidate data. Skips invalid records and deduplicates."""
    return _transform_records(raw_candidates, CandidateIn, "candidate_id", "candidate")


def transform_committees(raw_committees: List[Dict[str, Any]]) -> List[CommitteeIn]:
    """Transform raw FEC committee data. Skips invalid records and deduplicates."""
    return _transform_records(raw_committees, CommitteeIn, "committee_id", "committee")


def transform_inside_totals_by_candidate(
    raw_records: List[Dict[str, Any]],
) -> List[InsideTotalsByCandidateIn]:
    """Transform raw FEC candidate totals into inside spending records.

    /candidates/totals/ returns multiple rows per candidate (e.g. primary +
    general election rows). Accumulates receipts and disbursements across all
    rows for the same (candidate_id, cycle) before validating.
    """
    accumulated: dict[tuple, dict] = {}

    for idx, item in enumerate(raw_records):
        candidate_id = item.get("candidate_id")
        cycle = item.get("cycle")

        if not candidate_id or not cycle:
            logger.warning(
                f"Skipping inside totals row at index {idx}: missing "
                f"candidate_id or cycle"
            )
            continue

        key = (candidate_id, cycle)
        if key not in accumulated:
            accumulated[key] = {
                "candidate_id": candidate_id,
                "cycle": cycle,
                "receipts": 0.0,
                "disbursements": 0.0,
            }

        accumulated[key]["receipts"] += float(item.get("receipts") or 0)
        accumulated[key]["disbursements"] += float(item.get("disbursements") or 0)

    results = []
    for data in accumulated.values():
        try:
            results.append(InsideTotalsByCandidateIn.model_validate(data))
        except ValidationError as e:
            logger.warning(
                f"Skipping inside totals for {data.get('candidate_id')}: {e}"
            )
        except Exception as e:
            logger.error(
                f"Unexpected crash on inside totals for {data.get('candidate_id')}: {e}"
            )

    logger.info(
        f"Successfully transformed {len(results)} inside totals from "
        f"{len(raw_records)} records."
    )
    return results
