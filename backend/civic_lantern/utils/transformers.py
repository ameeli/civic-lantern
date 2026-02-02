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

    logger.info(
        f"Successfully transformed {len(transformed)}/{len(raw_candidates)} records."
    )

    return transformed
