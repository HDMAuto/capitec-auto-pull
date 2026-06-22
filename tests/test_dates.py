from datetime import datetime, timezone
from capitec_pull.dates import yesterday_sast, SAST

def test_yesterday_is_day_before_in_sast():
    now = datetime(2026, 6, 22, 9, 0, 0, tzinfo=SAST)
    assert yesterday_sast(now) == "2026-06-21"

def test_just_after_midnight_sast_still_uses_sast_calendar_day():
    now = datetime(2026, 6, 22, 0, 30, 0, tzinfo=SAST)
    assert yesterday_sast(now) == "2026-06-21"

def test_utc_input_is_converted_to_sast_first():
    now = datetime(2026, 6, 21, 23, 30, 0, tzinfo=timezone.utc)
    assert yesterday_sast(now) == "2026-06-21"

def test_to_ddmmyyyy_converts_iso_to_capitec_format():
    from capitec_pull.dates import to_ddmmyyyy
    assert to_ddmmyyyy("2026-06-21") == "21/06/2026"