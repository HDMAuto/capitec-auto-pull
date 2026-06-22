"""Build and write the folder-contract sidecar JSON for each branch pull."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional


def build_sidecar(
    *,
    branch_code: str,
    report_date: str,
    file: Optional[str],
    status: str,            # "pulled" | "no_card_sales" | "failed"
    row_count: Optional[int],
    error: Optional[str],
    pulled_at: str,
) -> dict:
    return {
        "branchCode": branch_code,
        "reportDate": report_date,
        "file": file,
        "status": status,
        "rowCount": row_count,
        "error": error,
        "pulledAt": pulled_at,
    }


def write_sidecar(path: str | Path, sidecar: dict) -> None:
    Path(path).write_text(json.dumps(sidecar, indent=2) + "\n")
