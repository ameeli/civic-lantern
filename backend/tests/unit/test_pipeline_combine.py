import logging

import pytest

from civic_lantern.db.models.committee import Committee
from civic_lantern.db.models.inside_totals_by_candidate import InsideTotalsByCandidate
from civic_lantern.db.models.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidate,
)
from civic_lantern.jobs.pipeline import (
    DateWindow,
    Ingestion,
    InvalidRowError,
    PerCycle,
    combine,
    validate,
)
from civic_lantern.schemas.committee import CommitteeIn
from civic_lantern.schemas.inside_totals_by_candidate import InsideTotalsByCandidateIn
from civic_lantern.schemas.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidateIn,
)
from civic_lantern.services.committee_corrections import CommitteeCorrections
from civic_lantern.services.fec_client import FECEndpoint

ENDPOINT = FECEndpoint(name="things", path="/things/", sort=("id",))
KEEP_FIRST = Ingestion(
    entity="schedule_e",
    scope=PerCycle(),
    endpoint=ENDPOINT,
    schema=ScheduleETotalsByCandidateIn,
    model=ScheduleETotalsByCandidate,
)
SUMMING = Ingestion(
    entity="inside_totals",
    scope=PerCycle(),
    endpoint=ENDPOINT,
    schema=InsideTotalsByCandidateIn,
    model=InsideTotalsByCandidate,
    sum_duplicates=("receipts", "disbursements"),
)


def _ie(candidate_id, indicator, total):
    return {
        "candidate_id": candidate_id,
        "cycle": 2024,
        "support_oppose_indicator": indicator,
        "total": total,
    }


def _totals(candidate_id, receipts, disbursements, cycle=2024):
    return {
        "candidate_id": candidate_id,
        "cycle": cycle,
        "receipts": receipts,
        "disbursements": disbursements,
    }


def _dump(rows):
    return [r.model_dump() for r in rows]


@pytest.mark.unit
class TestIngestionDeclaration:
    def test_key_columns_come_from_the_model(self):
        assert KEEP_FIRST.key_columns == (
            "candidate_id",
            "cycle",
            "support_oppose_indicator",
        )

    @pytest.mark.parametrize(
        "kwargs, message",
        [
            ({"sum_duplicates": ("nope",)}, "not on"),
            ({"sum_duplicates": ("cycle",)}, "can't sum primary key"),
            (
                {
                    "scope": DateWindow("min", "max"),
                    "corrections": CommitteeCorrections(),
                },
                "per-cycle",
            ),
        ],
    )
    def test_rejects_inconsistent_declarations(self, kwargs, message):
        base = {
            "entity": "inside_totals",
            "scope": PerCycle(),
            "endpoint": ENDPOINT,
            "schema": InsideTotalsByCandidateIn,
            "model": InsideTotalsByCandidate,
        }
        with pytest.raises(ValueError, match=message):
            Ingestion(**{**base, **kwargs})

    def test_partial_fetch_is_refused_when_rows_combine_pieces(self):
        corrected = Ingestion(
            entity="corrected",
            scope=PerCycle(),
            endpoint=ENDPOINT,
            schema=InsideTotalsByCandidateIn,
            model=InsideTotalsByCandidate,
            corrections=CommitteeCorrections(),
        )

        assert KEEP_FIRST.accepts_partial_fetch is True
        assert SUMMING.accepts_partial_fetch is False
        assert corrected.accepts_partial_fetch is False


@pytest.mark.unit
class TestCombineKeepFirst:
    def test_keeps_first_row_per_key_and_warns_once(self, caplog):
        rows = validate(
            [_ie("P1", "S", 1), _ie("P1", "O", 2), _ie("P1", "s", 3)], KEEP_FIRST
        )

        with caplog.at_level(logging.WARNING):
            combined = combine(rows, KEEP_FIRST)

        assert [(r.support_oppose_indicator.value, r.total) for r in combined] == [
            ("S", 1.0),
            ("O", 2.0),
        ]
        warnings = [r for r in caplog.records if "duplicate key" in r.message]
        assert len(warnings) == 1
        assert "1 duplicate key(s)" in warnings[0].message


@pytest.mark.unit
class TestCombineSum:
    def test_sums_named_fields_in_first_seen_order(self):
        rows = validate(
            [
                _totals("P2", 1.5, 1),
                _totals("P1", 10, None),
                _totals("P2", "2.25", 3),
                _totals("P1", None, 4),
            ],
            SUMMING,
        )

        assert _dump(combine(rows, SUMMING)) == [
            _totals("P2", 3.75, 4.0),
            _totals("P1", 10.0, 4.0),
        ]

    def test_a_single_row_with_none_amounts_becomes_zero(self):
        rows = validate([_totals("P1", None, None)], SUMMING)

        assert _dump(combine(rows, SUMMING)) == [_totals("P1", 0.0, 0.0)]


@pytest.mark.unit
class TestValidate:
    def test_skips_invalid_rows_with_a_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            rows = validate([_ie("P1", None, 1), _ie("P2", "S", 2)], KEEP_FIRST)

        assert [r.candidate_id for r in rows] == ["P2"]
        assert "support_oppose_indicator" in caplog.text

    @pytest.mark.parametrize("amount", ["", "abc"])
    def test_summing_ingestion_fails_on_a_bad_amount(self, amount):
        with pytest.raises(InvalidRowError, match="P1"):
            validate([_totals("P1", amount, 1)], SUMMING)

    def test_summing_ingestion_skips_rows_missing_their_key(self):
        rows = validate([_totals(None, 5, 5), _totals("P1", 1, 1)], SUMMING)

        assert [r.candidate_id for r in rows] == ["P1"]

    def test_keep_first_declarations_work_for_single_column_keys(self):
        committees = Ingestion(
            entity="committees",
            scope=DateWindow("min_first_file_date", "max_first_file_date"),
            endpoint=ENDPOINT,
            schema=CommitteeIn,
            model=Committee,
        )
        rows = validate(
            [
                {"committee_id": "C1", "name": "First"},
                {"committee_id": "C1", "name": "Second"},
            ],
            committees,
        )

        assert [r.name for r in combine(rows, committees)] == ["First"]
