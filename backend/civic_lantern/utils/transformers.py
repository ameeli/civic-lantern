import logging
from typing import Any, Dict, List, Type, TypeVar

from pydantic import BaseModel, ValidationError

from civic_lantern.schemas.candidate import CandidateIn
from civic_lantern.schemas.committee import CommitteeIn

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

    logger.info(
        f"Successfully transformed {len(deduped)}/{len(raw_records)} records."
    )

    return deduped


def transform_candidates(raw_candidates: List[Dict[str, Any]]) -> List[CandidateIn]:
    """Transform raw FEC candidate data. Skips invalid records and deduplicates."""
    return _transform_records(raw_candidates, CandidateIn, "candidate_id", "candidate")


def transform_committees(raw_committees: List[Dict[str, Any]]) -> List[CommitteeIn]:
    """Transform raw FEC committee data. Skips invalid records and deduplicates."""
    return _transform_records(raw_committees, CommitteeIn, "committee_id", "committee")
