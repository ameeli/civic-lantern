"""Integration tests for BaseService's generic upsert keyed on the full primary key."""

from decimal import Decimal

import pytest

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.enums import SupportOpposeEnum
from civic_lantern.db.models.inside_totals_by_candidate import InsideTotalsByCandidate
from civic_lantern.db.models.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidate,
)
from civic_lantern.services.data.base import BaseService


@pytest.mark.integration
@pytest.mark.asyncio
class TestCompositeKeyUpsert:
    async def test_conflict_key_is_the_full_primary_key(self, async_db):
        async_db.add(Candidate(candidate_id="P001", name="Alice"))
        await async_db.commit()
        service = BaseService(InsideTotalsByCandidate, db=async_db)

        rows = [
            {"candidate_id": "P001", "cycle": 2022, "receipts": 1, "disbursements": 1},
            {"candidate_id": "P001", "cycle": 2024, "receipts": 2, "disbursements": 2},
        ]
        first = await service.upsert_batch(rows)
        rows[1]["receipts"] = 5
        second = await service.upsert_batch(rows)

        assert (first["inserted"], second["updated"]) == (2, 1)
        stored = await async_db.get(
            InsideTotalsByCandidate, {"candidate_id": "P001", "cycle": 2024}
        )
        assert stored.receipts == Decimal("5.00")

    async def test_failed_rows_report_their_full_key(self, async_db):
        service = BaseService(ScheduleETotalsByCandidate, db=async_db)

        stats = await service.upsert_batch(
            [
                {
                    "candidate_id": "P_MISSING",
                    "cycle": 2024,
                    "support_oppose_indicator": SupportOpposeEnum.SUPPORT,
                    "total": 1,
                }
            ]
        )

        assert stats["errors"] == 1
        assert stats["failed_ids"] == [("P_MISSING", 2024, "S")]
