from datetime import date
from typing import Optional

# Historical backfill before 2024 is out of scope — this floor is never
# revisited by the nightly job. Cycles are never retired once active: as
# 2026, 2028, ... join the active range, nightly FEC request volume grows
# unbounded. Revisit if/when that becomes a real rate-limit problem.
MIN_CYCLE = 2024


def current_cycle_ceiling(today: Optional[date] = None) -> int:
    """The most recent even-numbered year, treated as the newest active cycle."""
    today = today or date.today()
    return today.year if today.year % 2 == 0 else today.year - 1


def active_cycles(today: Optional[date] = None) -> list[int]:
    """Every even-numbered cycle from MIN_CYCLE through the current ceiling."""
    ceiling = current_cycle_ceiling(today)
    if ceiling < MIN_CYCLE:
        return []
    return list(range(MIN_CYCLE, ceiling + 1, 2))
