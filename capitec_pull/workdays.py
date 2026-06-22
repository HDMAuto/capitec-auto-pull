"""Working-day check. Closed on Sundays and Public Holidays."""
from __future__ import annotations
from datetime import datetime
import holidays

_ZA = holidays.SouthAfrica()

def is_working_day(iso_date: str) -> bool:
    """True if the business trades on this date (Mon–Sat, not a ZA public holiday)."""
    d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    if d.weekday() == 6:
        return False
    if d in _ZA:
        return False
    return True