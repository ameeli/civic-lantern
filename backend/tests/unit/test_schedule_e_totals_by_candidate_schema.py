import pytest
from pydantic import ValidationError

from civic_lantern.schemas.schedule_e_totals_by_candidate import (
    ScheduleETotalsByCandidateIn,
)
from civic_lantern.utils.transformers import transform_schedule_e_totals_by_candidate

VALID_RAW = {
    "candidate_id": "P00009423",
    "cycle": 2024,
    "support_oppose_indicator": "S",
    "total": 2000000.0,
}


@pytest.mark.unit
class TestScheduleETotalsByCandidateIn:
    def test_valid_record(self):
        result = ScheduleETotalsByCandidateIn.model_validate(VALID_RAW)
        assert result.candidate_id == "P00009423"
        assert result.cycle == 2024
        assert result.support_oppose_indicator.value == "S"
        assert result.total == 2000000.0

    def test_missing_candidate_id_raises(self):
        with pytest.raises(ValidationError):
            ScheduleETotalsByCandidateIn.model_validate(
                {**VALID_RAW, "candidate_id": None}
            )

    def test_missing_indicator_raises(self):
        with pytest.raises(ValidationError):
            raw = {k: v for k, v in VALID_RAW.items() if k != "support_oppose_indicator"}
            ScheduleETotalsByCandidateIn.model_validate(raw)

    def test_invalid_indicator_raises(self):
        with pytest.raises(ValidationError):
            ScheduleETotalsByCandidateIn.model_validate(
                {**VALID_RAW, "support_oppose_indicator": "X"}
            )

    def test_indicator_normalized_to_uppercase(self):
        result = ScheduleETotalsByCandidateIn.model_validate(
            {**VALID_RAW, "support_oppose_indicator": "s"}
        )
        assert result.support_oppose_indicator.value == "S"

    def test_oppose_indicator_accepted(self):
        result = ScheduleETotalsByCandidateIn.model_validate(
            {**VALID_RAW, "support_oppose_indicator": "O"}
        )
        assert result.support_oppose_indicator.value == "O"

    def test_null_total_accepted(self):
        result = ScheduleETotalsByCandidateIn.model_validate(
            {**VALID_RAW, "total": None}
        )
        assert result.total is None


@pytest.mark.unit
class TestTransformScheduleETotalsByCandidate:
    def test_valid_row_passes_through(self):
        results = transform_schedule_e_totals_by_candidate([VALID_RAW])
        assert len(results) == 1
        assert results[0].candidate_id == "P00009423"

    def test_skips_null_candidate_id(self, caplog):
        raw = [{**VALID_RAW, "candidate_id": None}, VALID_RAW]
        results = transform_schedule_e_totals_by_candidate(raw)
        assert len(results) == 1
        assert any("missing" in r.message for r in caplog.records)

    def test_deduplicates_identical_composite_key(self):
        raw = [VALID_RAW, VALID_RAW]
        results = transform_schedule_e_totals_by_candidate(raw)
        assert len(results) == 1

    def test_support_and_oppose_are_separate(self):
        raw = [
            {**VALID_RAW, "support_oppose_indicator": "S"},
            {**VALID_RAW, "support_oppose_indicator": "O"},
        ]
        results = transform_schedule_e_totals_by_candidate(raw)
        assert len(results) == 2

    def test_empty_input_returns_empty(self):
        assert transform_schedule_e_totals_by_candidate([]) == []
