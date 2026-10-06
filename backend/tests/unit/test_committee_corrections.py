from datetime import date
from unittest.mock import AsyncMock, call

import pytest

from civic_lantern.services.committee_corrections import (
    COMMITTEE_REPORTS,
    COMMITTEE_TOTALS,
    CommitteeCorrections,
    CommitteeOverride,
    CommitteeSplit,
    CommitteeSplitDataError,
    CorrectionInputs,
)
from civic_lantern.services.fec_client import FECClient
from civic_lantern.utils.transformers import transform_inside_totals_by_candidate

CYCLE = 2024
BEFORE, AFTER = "P_BEFORE", "P_AFTER"
SPLIT = CommitteeSplit("C_SHARED", CYCLE, BEFORE, AFTER, date(2024, 7, 21))
OVERRIDE = CommitteeOverride("P_OVERRIDE", CYCLE, "C_DROPPED")


def _report(start: str, end: str, receipts: float, disbursements: float, **extra):
    return {
        "coverage_start_date": start,
        "coverage_end_date": end,
        "total_receipts_period": receipts,
        "total_disbursements_period": disbursements,
        "most_recent": True,
        **extra,
    }


def _row(candidate_id: str, receipts: float, disbursements: float) -> dict:
    return {
        "candidate_id": candidate_id,
        "cycle": CYCLE,
        "receipts": receipts,
        "disbursements": disbursements,
    }


def _by_candidate(rows: list) -> dict:
    return {r["candidate_id"]: r for r in rows}


@pytest.mark.unit
class TestApplySplits:
    corrections = CommitteeCorrections(overrides=(), splits=(SPLIT,))

    def test_replaces_both_candidates_duplicated_rows(self):
        raw = [_row(BEFORE, 1000, 900), _row(AFTER, 1000, 900), _row("OTHER", 1, 1)]
        inputs = CorrectionInputs(
            committee_reports={"C_SHARED": [_report("2024-01-01", "2024-06-30", 6, 5)]}
        )

        rows = self.corrections.apply(raw, CYCLE, inputs)

        assert rows == [
            _row("OTHER", 1, 1),
            _row(BEFORE, 6.0, 5.0),
            _row(AFTER, 0.0, 0.0),
        ]

    def test_prorates_straddling_report_by_day_count(self):
        # July has 31 days; split_date 2024-07-21 gives 20 days before, 11 after.
        inputs = CorrectionInputs(
            committee_reports={
                "C_SHARED": [
                    _report("2024-06-01", "2024-06-30", 100.0, 50.0),
                    _report("2024-07-01", "2024-07-31", 31.0, 62.0),
                    _report("2024-08-01", "2024-08-31", 200.0, 90.0),
                ]
            }
        )

        rows = _by_candidate(self.corrections.apply([], CYCLE, inputs))

        assert rows[BEFORE]["receipts"] == pytest.approx(100.0 + 20.0)
        assert rows[BEFORE]["disbursements"] == pytest.approx(50.0 + 40.0)
        assert rows[AFTER]["receipts"] == pytest.approx(200.0 + 11.0)
        assert rows[AFTER]["disbursements"] == pytest.approx(90.0 + 22.0)

    def test_ignores_superseded_amendments(self):
        inputs = CorrectionInputs(
            committee_reports={
                "C_SHARED": [
                    _report("2024-01-01", "2024-01-31", 10.0, 0.0, most_recent=False),
                    _report("2024-01-01", "2024-01-31", 999.0, 0.0),
                ]
            }
        )

        rows = _by_candidate(self.corrections.apply([], CYCLE, inputs))

        assert rows[BEFORE]["receipts"] == 999.0

    def test_keeps_first_when_a_period_has_two_most_recent_reports(self):
        inputs = CorrectionInputs(
            committee_reports={
                "C_SHARED": [
                    _report("2024-01-01", "2024-01-31", 5.0, 0.0),
                    _report("2024-01-01", "2024-01-31", 7.0, 0.0),
                ]
            }
        )

        rows = _by_candidate(self.corrections.apply([], CYCLE, inputs))

        assert rows[BEFORE]["receipts"] == 5.0

    @pytest.mark.parametrize(
        "reports",
        [[], [_report("2024-01-01", "2024-01-31", 10.0, 0.0, most_recent=False)]],
        ids=["no_reports", "none_most_recent"],
    )
    def test_raises_without_usable_reports(self, reports):
        inputs = CorrectionInputs(committee_reports={"C_SHARED": reports})

        with pytest.raises(CommitteeSplitDataError):
            self.corrections.apply([_row(BEFORE, 1, 1)], CYCLE, inputs)


@pytest.mark.unit
class TestApplyOverrides:
    corrections = CommitteeCorrections(overrides=(OVERRIDE,), splits=())

    def test_adds_dropped_committee_totals_alongside_fec_row(self):
        raw = [_row("P_OVERRIDE", 100, 90)]
        inputs = CorrectionInputs(
            committee_totals={"C_DROPPED": [{"receipts": 50, "disbursements": 40}]}
        )

        rows = self.corrections.apply(raw, CYCLE, inputs)

        assert rows == [_row("P_OVERRIDE", 100, 90), _row("P_OVERRIDE", 50, 40)]


@pytest.mark.unit
class TestApplyGeneral:
    corrections = CommitteeCorrections(overrides=(OVERRIDE,), splits=(SPLIT,))

    def test_other_cycles_pass_through_unchanged(self):
        raw = [_row(BEFORE, 1000, 900), _row("P_OVERRIDE", 100, 90)]

        assert self.corrections.apply(raw, 2020, CorrectionInputs()) == raw

    def test_does_not_mutate_raw_rows(self):
        raw = [_row(BEFORE, 1000, 900)]
        inputs = CorrectionInputs(
            committee_totals={"C_DROPPED": [{"receipts": 1, "disbursements": 1}]},
            committee_reports={"C_SHARED": [_report("2024-01-01", "2024-01-31", 1, 1)]},
        )

        self.corrections.apply(raw, CYCLE, inputs)

        assert raw == [_row(BEFORE, 1000, 900)]

    def test_split_and_override_compose_for_the_same_candidate(self):
        """The transform sums an after-split share with that candidate's own
        override committee, as for Harris in 2024."""
        corrections = CommitteeCorrections(
            overrides=(CommitteeOverride(AFTER, CYCLE, "C_SOLO"),), splits=(SPLIT,)
        )
        inputs = CorrectionInputs(
            committee_totals={"C_SOLO": [{"receipts": 0.0, "disbursements": 7.0}]},
            committee_reports={
                "C_SHARED": [
                    _report("2024-01-01", "2024-06-30", 500.0, 400.0),
                    _report("2024-07-01", "2024-07-31", 31.0, 31.0),
                    _report("2024-08-01", "2024-12-31", 700.0, 600.0),
                ]
            },
        )
        raw = [_row(BEFORE, 1_175_189_365.41, 1), _row(AFTER, 1_175_189_365.41, 1)]

        rows = corrections.apply(raw, CYCLE, inputs)
        totals = {r.candidate_id: r for r in transform_inside_totals_by_candidate(rows)}

        assert totals[BEFORE].receipts == pytest.approx(500.0 + 20.0)
        assert totals[AFTER].receipts == pytest.approx(700.0 + 11.0)
        assert totals[AFTER].disbursements == pytest.approx(600.0 + 11.0 + 7.0)


@pytest.mark.unit
@pytest.mark.asyncio
class TestFetchInputs:
    async def test_fetches_only_this_cycles_committees(self):
        corrections = CommitteeCorrections(
            overrides=(OVERRIDE, CommitteeOverride("P_OLD", 2020, "C_OLD")),
            splits=(SPLIT,),
        )
        client = AsyncMock(spec=FECClient)
        responses = {
            COMMITTEE_TOTALS: [{"receipts": 1}],
            COMMITTEE_REPORTS: [{"most_recent": True}],
        }
        client.fetch_all.side_effect = lambda endpoint, **_: responses[endpoint]

        inputs = await corrections.fetch_inputs(client, CYCLE)

        assert client.fetch_all.await_args_list == [
            call(COMMITTEE_TOTALS, committee_id="C_DROPPED", cycle=CYCLE),
            call(COMMITTEE_REPORTS, committee_id="C_SHARED", cycle=CYCLE),
        ]
        assert inputs == CorrectionInputs(
            committee_totals={"C_DROPPED": [{"receipts": 1}]},
            committee_reports={"C_SHARED": [{"most_recent": True}]},
        )

    async def test_makes_no_calls_for_a_cycle_without_corrections(self):
        client = AsyncMock(spec=FECClient)

        inputs = await CommitteeCorrections().fetch_inputs(client, 1900)

        client.fetch_all.assert_not_awaited()
        assert inputs == CorrectionInputs()
