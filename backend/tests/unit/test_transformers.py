import pytest
from pydantic import ValidationError

from civic_lantern.schemas.candidate import CandidateIn
from civic_lantern.utils.transformers import transform_candidates


@pytest.mark.unit
class TestCandidateValidation:
    """Test Pydantic validation catches bad data."""

    def test_valid_candidate(self):
        """Baseline: valid data passes."""
        raw = {
            "candidate_id": "P00003392",
            "name": "OBAMA, BARACK",
            "office": "P",
            "state": "IL",
            "party": "DEM",
        }
        result = CandidateIn.model_validate(raw)
        assert result.candidate_id == "P00003392"
        assert result.name == "Barack Obama"

    def test_missing_required_fields(self):
        """Missing candidate_id or name should fail."""
        with pytest.raises(ValidationError):
            CandidateIn.model_validate({"office": "H"})

    def test_null_handling(self):
        raw = {
            "candidate_id": "C001",
            "name": "SMITH, JOHN",
            "district": None,
            "state": "",
        }
        result = CandidateIn.model_validate(raw)
        assert result.candidate_id == "C001"
        assert result.district is None
        assert result.state == ""

    def test_district_padding(self):
        raw = {"candidate_id": "C001", "name": "Test", "district": "9"}
        result = CandidateIn.model_validate(raw)
        assert result.district == "09"

    def test_transform_skips_invalid(self, caplog):
        """Transformer should skip bad records, not crash."""
        raw_list = [
            {"candidate_id": "C001", "name": "Valid"},
            {"name": "No ID"},
            {"candidate_id": "C003", "name": "Also Valid"},
        ]
        results = transform_candidates(raw_list)
        assert len(results) == 2
        assert results[0].candidate_id == "C001"
        assert any("Skipping candidate" in record.message for record in caplog.records)

    def test_office_normalization(self):
        """Office code should be uppercased."""
        raw = {
            "candidate_id": "C001",
            "name": "Test",
            "office": "h",
        }
        result = CandidateIn.model_validate(raw)
        assert result.office.value == "H"

    @pytest.mark.parametrize(
        "input_name, expected",
        [
            ("OBAMA, BARACK", "Barack Obama"),
            ("O'MALLEY, MARTIN", "Martin O'Malley"),
            ("DE'ANGELO, JOHN", "John De'Angelo"),
            ("DE LA ROSA, JOSE", "Jose De La Rosa"),
            ("JONES, TOM, JR", "Tom Jones Jr"),
            ("JONES, TOM III", "Tom Jones III"),
            ("SingleName", "Singlename"),
        ],
        ids=[
            "standard_name",
            "apostrophe_name",
            "multiple_before_apostrophe",
            "spaces_in_surname",
            "multiple_commas",
            "suffix",
            "single_name",
        ],
    )
    def test_name_normalization_scenarios(self, input_name, expected):
        raw = {"candidate_id": "C001", "name": input_name}
        result = CandidateIn.model_validate(raw)
        assert result.name == expected
