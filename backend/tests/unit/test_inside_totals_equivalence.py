"""The inside totals pipeline gives exactly what the pre-pipeline transform gave.

_legacy_transform is transform_inside_totals_by_candidate copied verbatim from
utils/transformers.py before it was deleted.
"""

import logging
import random
from typing import Any, Dict, List

import pytest
from pydantic import ValidationError

from civic_lantern.jobs.ingestors.inside_totals_by_candidate import (
    INSIDE_TOTALS_INGESTION,
)
from civic_lantern.jobs.pipeline import combine, validate
from civic_lantern.schemas.inside_totals_by_candidate import InsideTotalsByCandidateIn

logger = logging.getLogger(__name__)


def _legacy_transform(
    raw_records: List[Dict[str, Any]],
) -> List[InsideTotalsByCandidateIn]:
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

    return results


def _pipeline(rows):
    ingestion = INSIDE_TOTALS_INGESTION
    return combine(validate(rows, ingestion), ingestion)


def _random_amount(rng: random.Random):
    return rng.choice(
        [
            None,
            0,
            rng.randint(0, 10**9),
            rng.uniform(0, 1e9),
            round(rng.uniform(0, 1e6), 2),
            str(round(rng.uniform(0, 1e6), 2)),
            str(rng.randint(0, 10**6)),
        ]
    )


def _random_rows(rng: random.Random, n: int) -> List[Dict[str, Any]]:
    # A small key pool, so most keys repeat and get summed.
    ids = [f"P{i:03d}" for i in range(40)]
    rows = []
    for _ in range(n):
        row = {"candidate_id": rng.choice(ids), "cycle": rng.choice([2022, 2024])}
        for field in ("receipts", "disbursements"):
            if rng.random() < 0.9:  # sometimes absent entirely
                row[field] = _random_amount(rng)
        if rng.random() < 0.02:
            row["candidate_id"] = rng.choice([None, ""])  # skipped by both
        rows.append(row)
    return rows


@pytest.mark.unit
@pytest.mark.parametrize("seed", range(20))
def test_random_rows_match_the_legacy_transform(seed):
    rows = _random_rows(random.Random(seed), 500)

    assert [r.model_dump() for r in _pipeline(rows)] == [
        r.model_dump() for r in _legacy_transform(rows)
    ]
