from datetime import date

import pytest

from civic_lantern.core.cycles import MIN_CYCLE, active_cycles, current_cycle_ceiling


@pytest.mark.unit
class TestCurrentCycleCeiling:
    def test_even_year_returns_itself(self):
        assert current_cycle_ceiling(date(2026, 3, 1)) == 2026

    def test_odd_year_returns_prior_even_year(self):
        assert current_cycle_ceiling(date(2025, 3, 1)) == 2024


@pytest.mark.unit
class TestActiveCycles:
    def test_returns_every_even_cycle_from_floor_to_ceiling(self):
        assert active_cycles(date(2026, 3, 1)) == [2024, 2026]

    def test_odd_year_ceiling_falls_back_to_prior_even_year(self):
        assert active_cycles(date(2027, 3, 1)) == [2024, 2026]

    def test_single_cycle_when_ceiling_equals_floor(self):
        assert active_cycles(date(2024, 6, 1)) == [MIN_CYCLE]

    def test_empty_when_ceiling_below_floor(self):
        assert active_cycles(date(2022, 6, 1)) == []
