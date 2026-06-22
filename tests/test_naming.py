from capitec_pull.naming import output_basename, csv_path, sidecar_path, count_csv_rows

def test_basename_combines_date_and_branch():
    assert output_basename("2026-06-22", "101") == "2026-06-22_101"

def test_csv_and_sidecar_paths(tmp_path):
    assert csv_path(tmp_path, "2026-06-22", "101") == tmp_path / "2026-06-22_101.csv"
    assert sidecar_path(tmp_path, "2026-06-22", "101") == tmp_path / "2026-06-22_101.json"

def test_count_rows_excludes_header(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("Header A,Header B\nr1,1\nr2,2\nr3,3\n")
    assert count_csv_rows(p) == 3

def test_count_rows_empty_or_header_only(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("Header A,Header B\n")
    assert count_csv_rows(p) == 0