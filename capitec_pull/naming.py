"""Filename conventions and a best-effort CSV row counter."""
from __future__ import annotations
from pathlib import Path

def output_basename(report_date: str, branch_code: str) -> str:
    return f"{report_date}_{branch_code}"

def csv_path(folder: Path, report_date: str, branch_code: str) -> Path:
    return Path(folder) / f"{output_basename(report_date, branch_code)}.csv"

def sidecar_path(folder: Path, report_date: str, branch_code: str) -> Path:
    return Path(folder) / f"{output_basename(report_date, branch_code)}.json"

def count_csv_rows(path: str | Path) -> int:
    """Count data rows (non-empty lines minus the header). Best-effort."""
    lines = [ln for ln in Path(path).read_text().splitlines() if ln.strip()]
    return max(0, len(lines) - 1)