import pytest
from pydantic import ValidationError

from civic_lantern.schemas.inside_totals_by_candidate import InsideTotalsByCandidateIn
from civic_lantern.utils.transformers import transform_inside_totals_by_candidate

VALID_RAW = {
    "candidate_id": "P00009423",
    "cycle": 2024,
    "receipts": 500000.0,
    "disbursements": 480000.0,
}


@pytest.mark.unit
class TestInsideTotalsByCandidateIn:
    def test_valid_record(self):
        result = InsideTotalsByCandidateIn.model_validate(VALID_RAW)
        assert result.candidate_id == "P00009423"
        assert result.cycle == 2024
        assert result.receipts == 500000.0
        assert result.disbursements == 480000.0

    def test_missing_candidate_id_raises(self):
        with pytest.raises(ValidationError):
            InsideTotalsByCandidateIn.model_validate({"cycle": 2024})

    def test_missing_cycle_raises(self):
        with pytest.raises(ValidationError):
            InsideTotalsByCandidateIn.model_validate({"candidate_id": "P00009423"})

    def test_null_amounts_accepted(self):
        result = InsideTotalsByCandidateIn.model_validate(
            {**VALID_RAW, "receipts": None, "disbursements": None}
        )
        assert result.receipts is None
        assert result.disbursements is None

    def test_absent_amounts_default_to_none(self):
        result = InsideTotalsByCandidateIn.model_validate(
            {"candidate_id": "P00009423", "cycle": 2024}
        )
        assert result.receipts is None
        assert result.disbursements is None


@pytest.mark.unit
class TestTransformInsideTotalsByCandidate:
    def test_single_row_per_candidate(self):
        results = transform_inside_totals_by_candidate([VALID_RAW])
        assert len(results) == 1
        assert results[0].receipts == 500000.0

    def test_accumulates_multiple_rows_per_candidate(self):
        """Multiple election-type rows per candidate are summed."""
        raw = [
            {**VALID_RAW, "receipts": 100.0, "disbursements": 90.0},
            {**VALID_RAW, "receipts": 50.0, "disbursements": 40.0},
        ]
        results = transform_inside_totals_by_candidate(raw)
        assert len(results) == 1
        assert results[0].receipts == 150.0
        assert results[0].disbursements == 130.0

    def test_separate_candidates_produce_separate_rows(self):
        raw = [
            {**VALID_RAW, "candidate_id": "P001"},
            {**VALID_RAW, "candidate_id": "P002"},
        ]
        results = transform_inside_totals_by_candidate(raw)
        assert len(results) == 2

    def test_same_candidate_different_cycles_kept_separate(self):
        raw = [
            {**VALID_RAW, "cycle": 2024},
            {**VALID_RAW, "cycle": 2022},
        ]
        results = transform_inside_totals_by_candidate(raw)
        assert len(results) == 2

    def test_null_amounts_treated_as_zero_in_accumulation(self):
        raw = [
            {**VALID_RAW, "receipts": None, "disbursements": None},
            {**VALID_RAW, "receipts": 50.0, "disbursements": 40.0},
        ]
        results = transform_inside_totals_by_candidate(raw)
        assert len(results) == 1
        assert results[0].receipts == 50.0

    def test_skips_rows_missing_required_fields(self, caplog):
        raw = [
            {"cycle": 2024, "receipts": 100.0},
            VALID_RAW,
        ]
        results = transform_inside_totals_by_candidate(raw)
        assert len(results) == 1
        assert any("missing candidate_id" in r.message for r in caplog.records)

    def test_empty_input_returns_empty(self):
        assert transform_inside_totals_by_candidate([]) == []
