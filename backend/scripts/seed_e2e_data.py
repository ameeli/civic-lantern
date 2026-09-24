"""Seeds synthetic candidate spending data for cycle 2024 so the Playwright
e2e suite has real bubbles to test against in CI.

Not real FEC data: a CI job can't safely call the rate-limited FEC API on
every run, so this inserts synthetic-but-representative rows directly and
marks the cycle "ready" the same way a real ingestion run would. Idempotent
— re-running deletes and re-inserts its own rows (identified by the
E2ESEED candidate_id prefix) rather than accumulating duplicates.

Destructive: it also deletes every cycle-2024 IngestionRun row for the
spending ingestors, so it refuses to run unless ALLOW_SEED_E2E_DATA=1 is set.
Only set that against a disposable database (e.g. the CI Postgres service).
"""

import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, text

from civic_lantern.db.models.candidate import Candidate
from civic_lantern.db.models.enums import OfficeTypeEnum, SupportOpposeEnum
from civic_lantern.db.models.ingestion_run import IngestionRun, IngestionRunStatus
from civic_lantern.db.models.inside_totals_by_candidate import InsideTotalsByCandidate
from civic_lantern.db.models.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidate,
)
from civic_lantern.db.session import JobSessionLocal

CYCLE = 2024
CANDIDATE_ID_PREFIX = "E2ESEED"
SPENDING_INGESTOR_NAMES = [
    "inside_totals_by_candidate",
    "schedule_e_totals_by_candidate",
]

STATES = ["CA", "TX", "NY", "FL", "PA", "OH", "GA", "NC", "MI", "AZ"]
PARTIES = ["DEM", "REP"]

# (office, candidate count, top spender's disbursements) - Senate needs >=30
# for the frontend's default top-30 slider range to have real headroom.
OFFICE_ROSTERS = [
    (OfficeTypeEnum.SENATE, 35, 20_000_000),
    (OfficeTypeEnum.HOUSE, 10, 5_000_000),
    (OfficeTypeEnum.PRESIDENT, 5, 100_000_000),
]


def _roster(office: OfficeTypeEnum, count: int, top_disbursements: int) -> list[dict]:
    rows = []
    for i in range(count):
        disbursements = Decimal(top_disbursements) * Decimal(count - i) / Decimal(count)
        rows.append(
            {
                "candidate_id": f"{CANDIDATE_ID_PREFIX}{office.value}{i:03d}",
                "name": f"E2E Test Candidate {office.value}{i:03d}",
                "office": office,
                "party": PARTIES[i % len(PARTIES)],
                "state": STATES[i % len(STATES)],
                "disbursements": disbursements,
                "receipts": disbursements * Decimal("1.1"),
                "support": disbursements * Decimal("0.25"),
                "oppose": disbursements * Decimal("0.1"),
            }
        )
    return rows


async def seed() -> None:
    if os.environ.get("ALLOW_SEED_E2E_DATA") != "1":
        raise SystemExit(
            "Refusing to seed: this script deletes real cycle-2024 ingestion "
            "history and inserts synthetic candidates. Set ALLOW_SEED_E2E_DATA=1 "
            "only when DATABASE_URL_ASYNC points at a disposable database."
        )
    async with JobSessionLocal() as session:
        await session.execute(
            delete(ScheduleETotalsByCandidate).where(
                ScheduleETotalsByCandidate.candidate_id.like(f"{CANDIDATE_ID_PREFIX}%")
            )
        )
        await session.execute(
            delete(InsideTotalsByCandidate).where(
                InsideTotalsByCandidate.candidate_id.like(f"{CANDIDATE_ID_PREFIX}%")
            )
        )
        await session.execute(
            delete(Candidate).where(
                Candidate.candidate_id.like(f"{CANDIDATE_ID_PREFIX}%")
            )
        )
        await session.execute(
            delete(IngestionRun).where(
                IngestionRun.ingestor_name.in_(SPENDING_INGESTOR_NAMES),
                IngestionRun.cycle == CYCLE,
            )
        )
        await session.flush()

        rows = [row for roster in OFFICE_ROSTERS for row in _roster(*roster)]

        for row in rows:
            session.add(
                Candidate(
                    candidate_id=row["candidate_id"],
                    name=row["name"],
                    office=row["office"],
                    party=row["party"],
                    party_full=row["party"],
                    state=row["state"],
                    district="00",
                    incumbent_challenge="C",
                    cycles=[CYCLE],
                )
            )
        await session.flush()

        for row in rows:
            session.add(
                InsideTotalsByCandidate(
                    candidate_id=row["candidate_id"],
                    cycle=CYCLE,
                    receipts=row["receipts"],
                    disbursements=row["disbursements"],
                )
            )
            session.add(
                ScheduleETotalsByCandidate(
                    candidate_id=row["candidate_id"],
                    cycle=CYCLE,
                    support_oppose_indicator=SupportOpposeEnum.SUPPORT,
                    total=row["support"],
                )
            )
            session.add(
                ScheduleETotalsByCandidate(
                    candidate_id=row["candidate_id"],
                    cycle=CYCLE,
                    support_oppose_indicator=SupportOpposeEnum.OPPOSE,
                    total=row["oppose"],
                )
            )

        now = datetime.now(timezone.utc)
        for ingestor_name in SPENDING_INGESTOR_NAMES:
            session.add(
                IngestionRun(
                    ingestor_name=ingestor_name,
                    cycle=CYCLE,
                    status=IngestionRunStatus.SUCCESS,
                    started_at=now,
                    last_run_completed_at=now,
                )
            )

        await session.flush()
        # mv_election_spending_summary is derived FROM mv_candidate_spending_summary,
        # so it must be refreshed second.
        await session.execute(
            text("REFRESH MATERIALIZED VIEW mv_candidate_spending_summary")
        )
        await session.execute(
            text("REFRESH MATERIALIZED VIEW mv_election_spending_summary")
        )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
