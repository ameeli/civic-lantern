from unittest.mock import patch

import pytest

from civic_lantern.jobs.ingestors.inside_totals_by_candidate import (
    KNOWN_COMMITTEE_OVERRIDES,
    KNOWN_COMMITTEE_SPLITS,
    CommitteeSplitDataError,
    InsideTotalsByCandidateIngestor,
)
from civic_lantern.services.data.inside_totals_by_candidate import (
    InsideTotalsByCandidateService,
)
from civic_lantern.utils.transformers import transform_inside_totals_by_candidate

# 2024 carries both a KNOWN_COMMITTEE_OVERRIDES entry and a
# KNOWN_COMMITTEE_SPLITS entry, so any test that exercises fetch(cycle=2024)
# without specifically testing that machinery needs get_committee_reports
# mocked too, or it must use a neutral cycle instead.
NEUTRAL_CYCLE = 2020


def _clean_report(start: str, end: str, receipts: float, disbursements: float) -> dict:
    return {
        "coverage_start_date": start,
        "coverage_end_date": end,
        "total_receipts_period": receipts,
        "total_disbursements_period": disbursements,
        "most_recent": True,
    }


@pytest.mark.unit
@pytest.mark.asyncio
class TestInsideTotalsByCandidateIngestor:
    async def test_fetch_calls_get_candidate_totals(self, mock_client, mock_session):
        """fetch() delegates to client.get_candidate_totals with correct cycle."""
        mock_client.get_candidate_totals.return_value = [
            {"candidate_id": "P001", "cycle": NEUTRAL_CYCLE}
        ]

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        result = await ingestor.fetch(cycle=NEUTRAL_CYCLE)

        mock_client.get_candidate_totals.assert_awaited_once_with(cycle=NEUTRAL_CYCLE)
        assert {"candidate_id": "P001", "cycle": NEUTRAL_CYCLE} in result

    async def test_fetch_merges_known_committee_overrides(
        self, mock_client, mock_session
    ):
        """For a cycle with a known override, fetch() patches in a synthetic
        row from that committee's own totals alongside the normal result."""
        trump_id, trump_cycle = "P80001571", 2024
        committee_id = KNOWN_COMMITTEE_OVERRIDES[(trump_id, trump_cycle)][0]

        mock_client.get_candidate_totals.return_value = []

        async def committee_totals(cid, cycle):
            if cid == committee_id:
                return [{"receipts": 495853270.30, "disbursements": 471501651.83}]
            return []

        mock_client.get_committee_totals.side_effect = committee_totals
        mock_client.get_committee_reports.return_value = [
            _clean_report("2024-01-01", "2024-12-31", 0.0, 0.0)
        ]

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        result = await ingestor.fetch(cycle=trump_cycle)

        mock_client.get_committee_totals.assert_any_await(
            committee_id, cycle=trump_cycle
        )
        assert {
            "candidate_id": trump_id,
            "cycle": trump_cycle,
            "receipts": 495853270.30,
            "disbursements": 471501651.83,
        } in result

    async def test_fetch_skips_overrides_for_other_cycles(
        self, mock_client, mock_session
    ):
        """A cycle with no known override doesn't call get_committee_totals."""
        mock_client.get_candidate_totals.return_value = []

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        result = await ingestor.fetch(cycle=1900)

        mock_client.get_committee_totals.assert_not_awaited()
        mock_client.get_committee_reports.assert_not_awaited()
        assert result == []

    async def test_fetch_without_cycle_raises_type_error(
        self, mock_client, mock_session
    ):
        """fetch() requires an explicit cycle — no more silent default."""
        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )

        with pytest.raises(TypeError):
            await ingestor.fetch()

    async def test_fetch_passes_explicit_cycle(self, mock_client, mock_session):
        """fetch() passes the provided cycle through to the client."""
        mock_client.get_candidate_totals.return_value = []

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        await ingestor.fetch(cycle=2022)

        mock_client.get_candidate_totals.assert_awaited_once_with(cycle=2022)

    @patch(
        "civic_lantern.jobs.ingestors.inside_totals_by_candidate.transform_inside_totals_by_candidate",
        autospec=True,
    )
    async def test_transform_delegates_to_transformer(
        self, mock_transform, mock_client, mock_session
    ):
        """transform() delegates to transform_inside_totals_by_candidate."""
        raw = [{"candidate_id": "P001", "cycle": 2024, "receipts": 100.0}]
        mock_transform.return_value = ["validated"]

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        result = ingestor.transform(raw)

        mock_transform.assert_called_once_with(raw)
        assert result == ["validated"]

    async def test_create_service_returns_correct_type(self, mock_client, mock_session):
        """create_service() returns correct service with the ingestor's session."""
        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        service = ingestor.create_service()

        assert isinstance(service, InsideTotalsByCandidateService)
        assert service.db is mock_session

    async def test_entity_name(self, mock_client, mock_session):
        """entity_name is 'inside_totals_by_candidate'."""
        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        assert ingestor.entity_name == "inside_totals_by_candidate"

    async def test_registered_in_registry(self, mock_client, mock_session):
        """InsideTotalsByCandidateIngestor is present in the ingestor registry."""
        from civic_lantern.jobs.ingestors import INGESTOR_REGISTRY

        assert "inside_totals_by_candidate" in INGESTOR_REGISTRY
        assert (
            INGESTOR_REGISTRY["inside_totals_by_candidate"]
            is InsideTotalsByCandidateIngestor
        )


@pytest.mark.unit
@pytest.mark.asyncio
class TestInsideTotalsByCandidateIngestorSplits:
    """KNOWN_COMMITTEE_SPLITS: a committee shared/double-counted across two
    candidate_ids (e.g. Biden -> Harris) gets excluded from the raw FEC
    fetch and replaced with a per-period computed split."""

    def _split_entry(self):
        (committee_id, cycle), split = next(iter(KNOWN_COMMITTEE_SPLITS.items()))
        return committee_id, cycle, split

    async def test_exclude_split_candidates_drops_both_candidate_rows(
        self, mock_client, mock_session
    ):
        """Raw FEC rows for both split candidates are stripped; unrelated
        candidates in the same cycle are untouched."""
        _, cycle, split = self._split_entry()
        before_id = split["before_candidate_id"]
        after_id = split["after_candidate_id"]

        mock_client.get_candidate_totals.return_value = [
            {
                "candidate_id": before_id,
                "cycle": cycle,
                "receipts": 1175189365.41,
                "disbursements": 1175214805.80,
            },
            {
                "candidate_id": after_id,
                "cycle": cycle,
                "receipts": 1175189365.41,
                "disbursements": 1175284546.82,
            },
            {
                "candidate_id": "UNRELATED",
                "cycle": cycle,
                "receipts": 1.0,
                "disbursements": 1.0,
            },
        ]
        mock_client.get_committee_totals.return_value = []
        mock_client.get_committee_reports.return_value = [
            _clean_report("2024-01-01", "2024-12-31", 0.0, 0.0)
        ]

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        result = await ingestor.fetch(cycle=cycle)

        assert {
            "candidate_id": "UNRELATED",
            "cycle": cycle,
            "receipts": 1.0,
            "disbursements": 1.0,
        } in result
        # The original duplicated 1175189365.41 FEC rows for the split
        # candidates must not survive fetch() in any form.
        assert not any(
            r["candidate_id"] in (before_id, after_id)
            and r["receipts"] == 1175189365.41
            for r in result
        )

    async def test_fetch_splits_prorates_straddling_report_by_day_count(
        self, mock_client, mock_session
    ):
        """The one report straddling split_date is apportioned by calendar
        day count; clean before/after reports pass through untouched."""
        committee_id, cycle, split = self._split_entry()
        before_id = split["before_candidate_id"]
        after_id = split["after_candidate_id"]

        mock_client.get_candidate_totals.return_value = []
        mock_client.get_committee_reports.return_value = [
            _clean_report("2024-06-01", "2024-06-30", 100.0, 50.0),
            # July: split_date is 2024-07-21, first day attributed to
            # after_id. 31-day period -> 20 days before / 11 days after.
            _clean_report("2024-07-01", "2024-07-31", 31.0, 62.0),
            _clean_report("2024-08-01", "2024-08-31", 200.0, 90.0),
        ]

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        result = await ingestor._fetch_splits(cycle)

        before_row = next(r for r in result if r["candidate_id"] == before_id)
        after_row = next(r for r in result if r["candidate_id"] == after_id)

        assert before_row["receipts"] == pytest.approx(100.0 + 20.0)
        assert before_row["disbursements"] == pytest.approx(50.0 + 40.0)
        assert after_row["receipts"] == pytest.approx(200.0 + 11.0)
        assert after_row["disbursements"] == pytest.approx(90.0 + 22.0)

    async def test_fetch_splits_dedupes_amended_reports_by_most_recent_flag(
        self, mock_client, mock_session
    ):
        """An amended report's superseded version must not be double-summed."""
        committee_id, cycle, split = self._split_entry()
        before_id = split["before_candidate_id"]

        mock_client.get_committee_reports.return_value = [
            {
                "coverage_start_date": "2024-01-01",
                "coverage_end_date": "2024-01-31",
                "total_receipts_period": 10.0,
                "total_disbursements_period": 0.0,
                "most_recent": False,
            },
            {
                "coverage_start_date": "2024-01-01",
                "coverage_end_date": "2024-01-31",
                "total_receipts_period": 999.0,
                "total_disbursements_period": 0.0,
                "most_recent": True,
            },
        ]

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        result = await ingestor._fetch_splits(cycle)

        before_row = next(r for r in result if r["candidate_id"] == before_id)
        assert before_row["receipts"] == 999.0

    async def test_fetch_splits_raises_when_no_most_recent_reports(
        self, mock_client, mock_session
    ):
        _, cycle, _ = self._split_entry()
        mock_client.get_committee_reports.return_value = [
            {
                "coverage_start_date": "2024-01-01",
                "coverage_end_date": "2024-01-31",
                "total_receipts_period": 10.0,
                "total_disbursements_period": 0.0,
                "most_recent": False,
            }
        ]

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        with pytest.raises(CommitteeSplitDataError):
            await ingestor._fetch_splits(cycle)

    async def test_fetch_skips_splits_for_other_cycles(self, mock_client, mock_session):
        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        result = await ingestor._fetch_splits(1900)

        mock_client.get_committee_reports.assert_not_awaited()
        assert result == []

    async def test_fetch_composes_split_and_override_rows_for_harris(
        self, mock_client, mock_session
    ):
        """Regression test for the Biden/Harris double-count: Harris's final
        total is her post-split share plus her solo committee's totals;
        Biden's final total is only his pre-split share; neither retains
        the original duplicated $1,175,189,365.41 anywhere."""
        committee_id, cycle, split = self._split_entry()
        before_id = split["before_candidate_id"]
        after_id = split["after_candidate_id"]
        override_committee_id = KNOWN_COMMITTEE_OVERRIDES[(after_id, cycle)][0]

        duplicated_row_before = {
            "candidate_id": before_id,
            "cycle": cycle,
            "receipts": 1175189365.41,
            "disbursements": 1175214805.80,
        }
        duplicated_row_after = {
            "candidate_id": after_id,
            "cycle": cycle,
            "receipts": 1175189365.41,
            "disbursements": 1175284546.82,
        }
        mock_client.get_candidate_totals.return_value = [
            duplicated_row_before,
            duplicated_row_after,
        ]
        mock_client.get_committee_reports.return_value = [
            _clean_report("2024-01-01", "2024-06-30", 500.0, 400.0),
            _clean_report("2024-07-01", "2024-07-31", 31.0, 31.0),
            _clean_report("2024-08-01", "2024-12-31", 700.0, 600.0),
        ]

        async def committee_totals(cid, cycle):
            if cid == override_committee_id:
                return [{"receipts": 0.0, "disbursements": 69741.02}]
            return []

        mock_client.get_committee_totals.side_effect = committee_totals

        ingestor = InsideTotalsByCandidateIngestor(
            client=mock_client, session=mock_session
        )
        raw = await ingestor.fetch(cycle=cycle)
        transformed = {
            row.candidate_id: row for row in transform_inside_totals_by_candidate(raw)
        }

        assert transformed[before_id].receipts == pytest.approx(500.0 + 20.0)
        assert transformed[before_id].disbursements == pytest.approx(400.0 + 20.0)
        assert transformed[after_id].receipts == pytest.approx(700.0 + 11.0)
        assert transformed[after_id].disbursements == pytest.approx(
            600.0 + 11.0 + 69741.02
        )
        assert duplicated_row_before["receipts"] not in (
            transformed[before_id].receipts,
            transformed[after_id].receipts,
        )
