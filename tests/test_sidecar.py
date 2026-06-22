import json
from capitec_pull.sidecar import build_sidecar, write_sidecar


def test_build_pulled_sidecar():
    s = build_sidecar(
        branch_code="101", report_date="2026-06-22",
        file="2026-06-22_101.csv", status="pulled",
        row_count=54, error=None, pulled_at="2026-06-22T05:10:00+02:00",
    )
    assert s == {
        "branchCode": "101",
        "reportDate": "2026-06-22",
        "file": "2026-06-22_101.csv",
        "status": "pulled",
        "rowCount": 54,
        "error": None,
        "pulledAt": "2026-06-22T05:10:00+02:00",
    }


def test_build_failed_sidecar_has_no_file():
    s = build_sidecar(
        branch_code="202", report_date="2026-06-22",
        file=None, status="failed",
        row_count=None, error="login timed out",
        pulled_at="2026-06-22T05:10:00+02:00",
    )
    assert s["status"] == "failed"
    assert s["file"] is None
    assert s["error"] == "login timed out"


def test_write_sidecar_roundtrips(tmp_path):
    path = tmp_path / "2026-06-22_101.json"
    s = build_sidecar(
        branch_code="101", report_date="2026-06-22",
        file="2026-06-22_101.csv", status="pulled",
        row_count=1, error=None, pulled_at="2026-06-22T05:10:00+02:00",
    )
    write_sidecar(path, s)
    assert json.loads(path.read_text()) == s