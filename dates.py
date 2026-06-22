"""Date helpers. 'Yesterday' is calendar day before today in SAST (UTC+2)."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta

#South African Standard Time - fixed UTC+2, no daylight savings.
SAST = timezone(timedelta(hours=2))

def yesterday_sast(now: datetime | None = None) -> str:
    """Return yesterday's date in SAST as 'YYYY-MM-DD'.

    `now` may be in any timezone; it is converted to SAST before the
    calendar day is taken. Defaults to the current time.
    """
    if now is None:
        now = datetime.now(SAST)
    now_sast = now.astimezone(SAST)
    return (now_sast - timedelta(days=1)).strftime("%Y-%m-%d")

def to_ddmmyyyy(iso_date: str) -> str:
    """Convert 'YYYY-MM-DD' to Capitec's 'DD/MM/YYYY' field format."""
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d/%m/%Y")