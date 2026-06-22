from capitec_pull.workdays import is_working_day

def test_saturday_is_working_day():
    assert is_working_day("2026-06-20") is True

def test_sunday_not_working_day():
    assert is_working_day("2026-06-21") is False

def test_weekday_is_a_working_day():
    assert is_working_day("2026-06-22") is True

def test_public_holiday_is_not_a_working_day():
    assert is_working_day("2026-06-16") is False