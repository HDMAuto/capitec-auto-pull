"""Entry point: pull a target day's Capitec CSV for every configured branch.

Default target = yesterday (SAST). Override with --date YYYY-MM-DD.
Sundays and ZA public holidays are skipped (business closed).
"""
from __future__ import annotations
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from .config_loader import load_branches, ConfigError
from .dates import yesterday_sast, SAST
from .workdays import is_working_day
from .naming import csv_path, sidecar_path, count_csv_rows
from .sidecar import build_sidecar, write_sidecar
from .capitec_client import browser_page, login, export_csv_for_date

CONFIG_PATH = Path(__file__).parent / "config.yaml"
PULLS_DIR = Path(__file__).parent / "pulls"
HEADLESS = os.environ.get("CAPITEC_HEADLESS", "").lower() in ("1", "true", "yes")


def pull_branch(branch, report_date: str, pulls_dir: Path) -> dict:
    """Pull one branch for report_date. Returns the sidecar dict (never raises)."""
    pulled_at = datetime.now(SAST).isoformat()
    try:
        with browser_page(headless=HEADLESS) as page:
            login(page, branch.username, branch.password)
            tmp = export_csv_for_date(page, pulls_dir, report_date)

        final = csv_path(pulls_dir, report_date, branch.branch_code)
        tmp.replace(final)
        rows = count_csv_rows(final)
        status = "pulled" if rows > 0 else "no_card_sales"
        return build_sidecar(
            branch_code=branch.branch_code, report_date=report_date,
            file=final.name, status=status, row_count=rows,
            error=None, pulled_at=pulled_at,
        )
    except Exception as err:  # isolate this branch's failure
        return build_sidecar(
            branch_code=branch.branch_code, report_date=report_date,
            file=None, status="failed", row_count=None,
            error=f"{type(err).__name__}: {err}", pulled_at=pulled_at,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull Capitec CSVs into pulls/.")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: yesterday SAST)")
    args = parser.parse_args()

    report_date = args.date or yesterday_sast()

    if not is_working_day(report_date):
        print(f"{report_date} is a Sunday or public holiday — nothing to pull.")
        return 0

    try:
        branches = load_branches(CONFIG_PATH)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 2

    PULLS_DIR.mkdir(exist_ok=True)
    print(f"Pulling Capitec CSVs for {report_date} ({len(branches)} branches)")

    failures = 0
    for branch in branches:
        print(f"  Branch {branch.branch_code}... ", end="", flush=True)
        sidecar = pull_branch(branch, report_date, PULLS_DIR)
        write_sidecar(sidecar_path(PULLS_DIR, report_date, branch.branch_code), sidecar)
        print(sidecar["status"] + (f" ({sidecar['error']})" if sidecar["error"] else ""))
        if sidecar["status"] == "failed":
            failures += 1

    print(f"Done. {len(branches) - failures} ok, {failures} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
