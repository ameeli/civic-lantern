import logging
from typing import Any, Dict, List

from pydantic import ValidationError

from civic_lantern.schemas.candidate import CandidateIn

logger = logging.getLogger(__name__)


def transform_candidates(raw_candidates: List[Dict[str, Any]]) -> List[CandidateIn]:
    """
    Transform raw FEC candidate data using Pydantic for validation and type parsing.
    Skips invalid records and logs them.
    """
    transformed = []

    for idx, raw in enumerate(raw_candidates):
        c_id = raw.get("candidate_id", f"index {idx}")

        try:
            candidate = CandidateIn.model_validate(raw)
            transformed.append(candidate)
        except ValidationError as e:
            logger.warning(f"Skipping candidate {c_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected crash on candidate {c_id}: {e}")

    # Deduplicate by candidate_id — FEC API can return the same candidate across
    # multiple pages. Keep the last occurrence (most recently seen data).
    seen: dict[str, CandidateIn] = {}
    for candidate in transformed:
        seen[candidate.candidate_id] = candidate
    deduped = list(seen.values())

    if len(deduped) < len(transformed):
        logger.warning(
            f"Dropped {len(transformed) - len(deduped)} duplicate candidate_id(s)."
        )

    logger.info(
        f"Successfully transformed {len(deduped)}/{len(raw_candidates)} records."
    )

    return deduped
