import pytest
from pydantic import ValidationError

from civic_lantern.schemas.committee import CommitteeIn

VALID_COMMITTEE = {
    "committee_id": "C00000422",
    "name": "NATIONAL BEER WHOLESALERS ASSN PAC",
    "committee_type": "Q",
    "state": "VA",
    "cycles": [2022, 2024],
}


@pytest.mark.unit
class TestCommitteeIn:
    def test_valid_committee(self):
        result = CommitteeIn.model_validate(VALID_COMMITTEE)
        assert result.committee_id == "C00000422"
        assert result.name == "NATIONAL BEER WHOLESALERS ASSN PAC"

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            CommitteeIn.model_validate({"committee_type": "Q"})

    def test_missing_committee_type(self):
        with pytest.raises(ValidationError):
            CommitteeIn.model_validate(
                {"committee_id": "C00000422", "name": "Test PAC"}
            )

    def test_committee_type_normalization(self):
        raw = {**VALID_COMMITTEE, "committee_type": "o"}
        result = CommitteeIn.model_validate(raw)
        assert result.committee_type.value == "O"

    def test_invalid_committee_type(self):
        with pytest.raises(ValidationError):
            CommitteeIn.model_validate({**VALID_COMMITTEE, "committee_type": "Z9"})

    def test_optional_fields_default_to_none(self):
        result = CommitteeIn.model_validate(VALID_COMMITTEE)
        assert result.designation is None
        assert result.affiliated_committee_name is None
        assert result.treasurer_name is None

    def test_list_fields_default_to_empty(self):
        raw = {
            "committee_id": "C00000422",
            "name": "Test PAC",
            "committee_type": "Q",
        }
        result = CommitteeIn.model_validate(raw)
        assert result.candidate_ids == []
        assert result.sponsor_candidate_ids == []
        assert result.cycles == []

    def test_whitespace_stripped(self):
        raw = {**VALID_COMMITTEE, "name": "  Test PAC  ", "state": " VA "}
        result = CommitteeIn.model_validate(raw)
        assert result.name == "Test PAC"
        assert result.state == "VA"

    @pytest.mark.parametrize(
        "committee_type,expected",
        [
            ("O", "O"),  # Super PAC
            ("Q", "Q"),  # PAC qualified
            ("X", "X"),  # Party non-qualified
            ("Y", "Y"),  # Party qualified
            ("I", "I"),  # Independent expenditure
        ],
        ids=[
            "super_pac",
            "pac_qualified",
            "party_nonqualified",
            "party_qualified",
            "ie_only",
        ],
    )
    def test_valid_committee_types(self, committee_type, expected):
        raw = {**VALID_COMMITTEE, "committee_type": committee_type}
        result = CommitteeIn.model_validate(raw)
        assert result.committee_type.value == expected
