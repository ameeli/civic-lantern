from decimal import Decimal

import pytest

from civic_lantern.schemas.spending import CandidateSpendingSchema


@pytest.mark.unit
class TestCandidateSpendingSchema:
    @pytest.mark.parametrize(
        "inside, support, oppose, expected_ratio, expected_vuln",
        [
            # Normal case (1:1 ratio)
            ("100.00", "60.00", "40.00", "1.00", "0.40"),
            # No denominator — returns None (no meaningful ratio)
            ("0.00", "50.00", "50.00", None, None),
            # Rounding check (1/3)
            ("300.00", "100.00", "0.00", "0.33", "0.00"),
            # No outside activity
            ("1000.00", "0.00", "0.00", "0.00", "0.00"),
            # High influence (Outside spend is 3x inside)
            ("100.00", "150.00", "150.00", "3.00", "1.50"),
            # All None inputs — no denominator, returns None
            (None, None, None, None, None),
            # Large Numbers (Ensure no precision loss)
            ("10000000.00", "5000000.00", "5000000.00", "1.00", "0.50"),
            # Very small amounts (Precision check)
            ("100.00", "0.01", "0.01", "0.00", "0.00"),  # Should round down to 0.00
        ],
    )
    def test_calculations(self, inside, support, oppose, expected_ratio, expected_vuln):
        """Test all ratio and vulnerability math in one go."""
        schema = CandidateSpendingSchema(
            candidate_id="P00003392",
            cycle=2024,
            inside_disbursements=inside,  # Pydantic converts strings to Decimal
            outside_support=support,
            outside_oppose=oppose,
        )

        expected_r = Decimal(expected_ratio) if expected_ratio is not None else None
        expected_v = Decimal(expected_vuln) if expected_vuln is not None else None
        assert schema.influence_ratio == expected_r
        assert schema.vulnerability_factor == expected_v

    def test_default_values(self):
        """Ensure defaults are None and computed fields return None without crashing."""
        schema = CandidateSpendingSchema(candidate_id="TEST", cycle=2024)
        assert schema.inside_receipts is None
        assert schema.influence_ratio is None
        assert schema.vulnerability_factor is None

    def test_inside_receipts_stored(self):
        """Ensure inside_receipts is stored and returned correctly."""
        schema = CandidateSpendingSchema(
            candidate_id="TEST", cycle=2024, inside_receipts="500.75"
        )
        assert schema.inside_receipts == Decimal("500.75")
