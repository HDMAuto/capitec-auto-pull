# Capitec CSV Pull Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **For this project specifically:** the user is typing the code by hand in their IDE, one step at a time. Treat the plan as a collaborative script — hand over each step's code, let the user create the files and run the commands, and confirm before moving on.

**Goal:** Log into the Capitec merchant portal for each of 3 branches, export yesterday's card-machine transactions as CSV, and stage each CSV plus a sidecar JSON in a folder for a separate "push" stage to upload into the HDM Portal.

**Architecture:** A small Python package. Pure, testable helpers (date, config, naming, sidecar) are built TDD-first. A Playwright-driven browser client (`capitec_client.py`) performs login → navigate → set Yesterday → export CSV, verified manually headed against the live site because selectors are unknown until observed. An orchestrator (`pull.py`) loops the branches, isolates per-branch failures, and writes the folder contract.

**Tech Stack:** Python 3.9+, Playwright (browser automation), PyYAML (config), pytest (tests).

---

## File Structure

```
capitec_pull/
  __init__.py
  config.example.yaml   committed template
  config.yaml           real credentials — GITIGNORED (user creates)
  dates.py              yesterday-in-SAST helper (pure)
  config_loader.py      load + validate config.yaml (pure)
  naming.py             filenames + CSV row count (pure)
  sidecar.py            build + write sidecar JSON (pure-ish: writes files)
  capitec_client.py     Playwright automation (manual verify)
  pull.py               orchestrator / entry point
  pulls/                output folder — GITIGNORED (created at runtime)
tests/
  test_dates.py
  test_config_loader.py
  test_naming.py
  test_sidecar.py
requirements.txt
.gitignore               (already committed)
README.md
```

Each pure module has one responsibility and is independently testable. `capitec_client.py`
knows only "given credentials, drive the browser, return the downloaded CSV path" — it does
not know the config format or the folder contract. `pull.py` is the only module that wires
everything together.

---

## Task 0: Project scaffolding & dependencies

**Files:**
- Create: `requirements.txt`
- Create: `capitec_pull/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Create `requirements.txt`**

```
playwright==1.44.0
PyYAML==6.0.1
holidays==0.49
pytest==8.2.0
```

(`holidays` provides South African public-holiday dates for the working-day check in Task 1b.)

- [ ] **Step 2: Create a virtual environment and install**

Run:
```bash
cd /Users/clivefigueira/CapitecCardPull
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```
Expected: pip installs cleanly; `playwright install chromium` downloads the browser.

- [ ] **Step 3: Create empty package markers**

```bash
mkdir -p capitec_pull tests
touch capitec_pull/__init__.py tests/__init__.py
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt capitec_pull/__init__.py tests/__init__.py
git commit -m "Add project scaffolding and dependencies"
```

---

## Task 1: Yesterday-in-SAST date helper

SAST (Africa/Johannesburg) is a fixed UTC+2 with no daylight saving, so we use a fixed
offset — no `tzdata` dependency needed. The function accepts an injectable `now` so it is
deterministic to test.

**Files:**
- Create: `capitec_pull/dates.py`
- Test: `tests/test_dates.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dates.py
from datetime import datetime, timezone, timedelta
from capitec_pull.dates import yesterday_sast, SAST

def test_yesterday_is_day_before_in_sast():
    now = datetime(2026, 6, 22, 9, 0, 0, tzinfo=SAST)
    assert yesterday_sast(now) == "2026-06-22".replace("22", "21")

def test_just_after_midnight_sast_still_uses_sast_calendar_day():
    # 00:30 SAST on the 22nd → yesterday is the 21st
    now = datetime(2026, 6, 22, 0, 30, 0, tzinfo=SAST)
    assert yesterday_sast(now) == "2026-06-21"

def test_utc_input_is_converted_to_sast_first():
    # 23:30 UTC on the 21st == 01:30 SAST on the 22nd → yesterday = 21st
    now = datetime(2026, 6, 21, 23, 30, 0, tzinfo=timezone.utc)
    assert yesterday_sast(now) == "2026-06-21"


def test_to_ddmmyyyy_converts_iso_to_capitec_format():
    from capitec_pull.dates import to_ddmmyyyy
    assert to_ddmmyyyy("2026-06-21") == "21/06/2026"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dates.py -v`
Expected: FAIL — `ModuleNotFoundError` / `ImportError: cannot import name 'yesterday_sast'`.

- [ ] **Step 3: Write minimal implementation**

```python
# capitec_pull/dates.py
"""Date helpers. 'Yesterday' is the calendar day before today in SAST (UTC+2)."""
from datetime import datetime, timezone, timedelta

# South Africa Standard Time — fixed UTC+2, no DST.
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dates.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add capitec_pull/dates.py tests/test_dates.py
git commit -m "Add date helpers (yesterday-in-SAST, DD/MM/YYYY)"
```

---

## Task 1b: Working-day check (skip Sundays + ZA public holidays)

**Files:**
- Create: `capitec_pull/workdays.py`
- Test: `tests/test_workdays.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workdays.py
from capitec_pull.workdays import is_working_day

def test_saturday_is_a_working_day():
    # 2026-06-20 is a Saturday
    assert is_working_day("2026-06-20") is True

def test_sunday_is_not_a_working_day():
    # 2026-06-21 is a Sunday
    assert is_working_day("2026-06-21") is False

def test_weekday_is_a_working_day():
    # 2026-06-22 is a Monday
    assert is_working_day("2026-06-22") is True

def test_public_holiday_is_not_a_working_day():
    # 2026-06-16 is Youth Day (SA public holiday), a Tuesday
    assert is_working_day("2026-06-16") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_workdays.py -v`
Expected: FAIL — cannot import `is_working_day`.

- [ ] **Step 3: Write minimal implementation**

```python
# capitec_pull/workdays.py
"""Working-day check. Closed on Sundays and South African public holidays."""
from __future__ import annotations
from datetime import datetime
import holidays

_ZA = holidays.SouthAfrica()


def is_working_day(iso_date: str) -> bool:
    """True if the business trades on this date (Mon–Sat, not a ZA public holiday)."""
    d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    if d.weekday() == 6:          # Sunday
        return False
    if d in _ZA:                  # South African public holiday
        return False
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_workdays.py -v`
Expected: PASS (4 passed). If the holiday test fails, confirm the installed `holidays`
version knows 2026 SA holidays (`python -c "import holidays; print('2026-06-16' in [str(d) for d in holidays.SouthAfrica(years=2026)])"`).

- [ ] **Step 5: Commit**

```bash
git add capitec_pull/workdays.py tests/test_workdays.py
git commit -m "Add working-day check (skip Sundays + ZA public holidays)"
```

---

## Task 2: Config loading & validation

**Files:**
- Create: `capitec_pull/config_loader.py`
- Create: `capitec_pull/config.example.yaml`
- Test: `tests/test_config_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config_loader.py
import pytest
from capitec_pull.config_loader import load_branches, ConfigError

VALID = """
branches:
  - branch_code: "101"
    username: "user101"
    password: "pass101"
  - branch_code: "202"
    username: "user202"
    password: "pass202"
"""

def _write(tmp_path, text):
    p = tmp_path / "config.yaml"
    p.write_text(text)
    return p

def test_loads_branches(tmp_path):
    branches = load_branches(_write(tmp_path, VALID))
    assert [b.branch_code for b in branches] == ["101", "202"]
    assert branches[0].username == "user101"
    assert branches[0].password == "pass101"

def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_branches(tmp_path / "nope.yaml")

def test_empty_branches_raises(tmp_path):
    with pytest.raises(ConfigError, match="at least one branch"):
        load_branches(_write(tmp_path, "branches: []\n"))

def test_missing_field_raises(tmp_path):
    bad = 'branches:\n  - branch_code: "101"\n    username: "u"\n'
    with pytest.raises(ConfigError, match="password"):
        load_branches(_write(tmp_path, bad))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_loader.py -v`
Expected: FAIL — cannot import `load_branches`.

- [ ] **Step 3: Write minimal implementation**

```python
# capitec_pull/config_loader.py
"""Load and validate config.yaml into a list of Branch records."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml


class ConfigError(Exception):
    """Raised when config.yaml is missing or malformed."""


@dataclass(frozen=True)
class Branch:
    branch_code: str
    username: str
    password: str


_REQUIRED = ("branch_code", "username", "password")


def load_branches(path: str | Path) -> list[Branch]:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    data = yaml.safe_load(path.read_text()) or {}
    raw = data.get("branches") or []
    if not raw:
        raise ConfigError("Config must define at least one branch")

    branches: list[Branch] = []
    for i, entry in enumerate(raw):
        entry = entry or {}
        for field in _REQUIRED:
            if not entry.get(field):
                raise ConfigError(
                    f"Branch #{i + 1} is missing required field: {field}"
                )
        branches.append(
            Branch(
                branch_code=str(entry["branch_code"]),
                username=str(entry["username"]),
                password=str(entry["password"]),
            )
        )
    return branches
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_loader.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Create the committed template `capitec_pull/config.example.yaml`**

```yaml
# Copy this file to config.yaml and fill in real credentials.
# config.yaml is gitignored — never commit real credentials.
branches:
  - branch_code: "101"
    username: "REPLACE_ME"
    password: "REPLACE_ME"
  - branch_code: "202"
    username: "REPLACE_ME"
    password: "REPLACE_ME"
  - branch_code: "303"
    username: "REPLACE_ME"
    password: "REPLACE_ME"
```

- [ ] **Step 6: Commit**

```bash
git add capitec_pull/config_loader.py capitec_pull/config.example.yaml tests/test_config_loader.py
git commit -m "Add config loading and validation"
```

---

## Task 3: Output naming & CSV row count

**Files:**
- Create: `capitec_pull/naming.py`
- Test: `tests/test_naming.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_naming.py
from pathlib import Path
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_naming.py -v`
Expected: FAIL — cannot import from `capitec_pull.naming`.

- [ ] **Step 3: Write minimal implementation**

```python
# capitec_pull/naming.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_naming.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add capitec_pull/naming.py tests/test_naming.py
git commit -m "Add output naming and CSV row count helpers"
```

---

## Task 4: Sidecar JSON builder & writer

**Files:**
- Create: `capitec_pull/sidecar.py`
- Test: `tests/test_sidecar.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sidecar.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sidecar.py -v`
Expected: FAIL — cannot import from `capitec_pull.sidecar`.

- [ ] **Step 3: Write minimal implementation**

```python
# capitec_pull/sidecar.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sidecar.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add capitec_pull/sidecar.py tests/test_sidecar.py
git commit -m "Add sidecar JSON builder and writer"
```

---

## Task 5: Capitec browser client — login (manual, headed)

This is the first browser task. Selectors are unknown, so we build a minimal headed login
and **discover the real selectors against the live site**, then fill them in. There is no
unit test — verification is visual.

**Files:**
- Create: `capitec_pull/capitec_client.py`

- [ ] **Step 1: Write the client skeleton with selector constants at the top**

```python
# capitec_pull/capitec_client.py
"""Playwright automation for the Capitec merchant portal.

One job: given a branch's credentials, drive the browser to export yesterday's
transactions as CSV and return the downloaded file path. Knows nothing about
config format or the folder contract.

SELECTORS ARE PLACEHOLDERS — verify each against the live site (Task 5/6) and
update. Prefer get_by_role / get_by_label / get_by_text over brittle CSS where
possible.
"""
from __future__ import annotations
from pathlib import Path
from contextlib import contextmanager
from playwright.sync_api import sync_playwright, Page

LOGIN_URL = "https://merchant.capitecbank.co.za/app/login"

# --- selectors to verify against the live site ---
SEL_USERNAME = "input[name='username']"      # TODO verify
SEL_PASSWORD = "input[name='password']"      # TODO verify
SEL_LOGIN_BTN = "button[type='submit']"      # TODO verify
# -------------------------------------------------

DEFAULT_TIMEOUT_MS = 30_000


@contextmanager
def browser_page(headless: bool = False):
    """Yield a fresh Playwright page with downloads enabled, then clean up."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        try:
            yield page
        finally:
            context.close()
            browser.close()


def login(page: Page, username: str, password: str) -> None:
    """Log into the merchant portal. Raises on failure (timeout / no nav)."""
    page.goto(LOGIN_URL)
    page.fill(SEL_USERNAME, username)
    page.fill(SEL_PASSWORD, password)
    page.click(SEL_LOGIN_BTN)
    # Wait for the SPA to leave the login page after auth.
    page.wait_for_url(lambda url: "login" not in url)
```

- [ ] **Step 2: Manual verification harness — log in for ONE branch, headed**

Create a throwaway `scratch_login.py` at the project root (do NOT commit):

```python
# scratch_login.py
from capitec_pull.config_loader import load_branches
from capitec_pull.capitec_client import browser_page, login

b = load_branches("capitec_pull/config.yaml")[0]
with browser_page(headless=False) as page:
    login(page, b.username, b.password)
    print("Logged in. Current URL:", page.url)
    input("Press Enter to close the browser...")
```

Run (after filling `config.yaml` with at least branch 101's real credentials):
```bash
source .venv/bin/activate
python scratch_login.py
```

Expected: a Chromium window opens, the login page loads. **If the fields don't fill or the
button isn't found**, that means a selector is wrong — see Step 3.

- [ ] **Step 3: Fix selectors from what you observe**

With the browser open on the login page, right-click the username field → Inspect, and read
the real attributes. Update `SEL_USERNAME`, `SEL_PASSWORD`, `SEL_LOGIN_BTN` accordingly.
Prefer stable attributes (`name`, `id`, `aria-label`, visible button text via
`page.get_by_role("button", name="...")`). Re-run `scratch_login.py` until the script logs
in and prints a non-login URL.

- [ ] **Step 4: Commit (client skeleton + verified login selectors only)**

```bash
git add capitec_pull/capitec_client.py
git commit -m "Add Capitec client with verified login flow"
```

(Do not add `scratch_login.py` — it stays local and uncommitted.)

---

## Task 6: Capitec browser client — custom-date range + export CSV

Continue in `capitec_pull/capitec_client.py`, verifying each selector live as in Task 5.
Uses the **Custom date** flow (Start = End = target date in `DD/MM/YYYY`), then Export → CSV.

**Files:**
- Modify: `capitec_pull/capitec_client.py`

- [ ] **Step 1: Add navigation + custom-date + export selectors and the export function**

Add below the login selectors (these are starting guesses based on the observed page —
verify each live, preferring `get_by_role`/`get_by_label`/`get_by_text`):

```python
# --- transactions / custom-date / export selectors to verify live ---
SEL_TRANSACTIONS_NAV = "text=Transactions"        # left-nav item   TODO verify
SEL_RANGE_BUTTON     = "text=Today"               # range button (label = current range) TODO verify
SEL_CUSTOM_DATE      = "text=Custom date"         # menu option     TODO verify
SEL_START_DATE       = "input[name='startDate']"  # Start date field TODO verify
SEL_END_DATE         = "input[name='endDate']"    # End date field   TODO verify
SEL_SAVE_RANGE       = "text=Save"                # Save button      TODO verify
SEL_EXPORT_BTN       = "text=Export"              # Export button    TODO verify
SEL_EXPORT_CSV       = "text=CSV"                 # CSV choice in export menu TODO verify
# ---------------------------------------------------------------------
```

Add the function (note: it takes the target date and types it; the range button's label is
the *current* range, so we don't hard-code "Today"):

```python
def export_csv_for_date(page: Page, download_dir: Path, ddmmyyyy: str) -> Path:
    """Assumes already logged in. Set the date range to a single day (start=end)
    via Custom date, export CSV, and save the download into download_dir.

    `ddmmyyyy` is the target date already formatted as 'DD/MM/YYYY'.
    Returns the saved file path. Raises if the export never starts.
    """
    page.click(SEL_TRANSACTIONS_NAV)
    page.click(SEL_RANGE_BUTTON)
    page.click(SEL_CUSTOM_DATE)

    # Single day: start and end are the same date.
    page.fill(SEL_START_DATE, ddmmyyyy)
    page.fill(SEL_END_DATE, ddmmyyyy)
    page.click(SEL_SAVE_RANGE)

    # Capture the browser download triggered by the export action.
    with page.expect_download() as dl_info:
        page.click(SEL_EXPORT_BTN)
        page.click(SEL_EXPORT_CSV)
    download = dl_info.value

    dest = Path(download_dir) / download.suggested_filename
    download.save_as(dest)
    return dest
```

- [ ] **Step 2: Manual verification — extend the scratch script to export a known date**

Update `scratch_login.py` (still uncommitted) to export a recent working day you know has
data (replace the date below):

```python
from pathlib import Path
from capitec_pull.config_loader import load_branches
from capitec_pull.capitec_client import browser_page, login, export_csv_for_date

b = load_branches("capitec_pull/config.yaml")[0]
out = Path("scratch_out"); out.mkdir(exist_ok=True)
with browser_page(headless=False) as page:
    login(page, b.username, b.password)
    saved = export_csv_for_date(page, out, "20/06/2026")  # a day you know had sales
    print("Saved:", saved)
    input("Press Enter to close...")
```

Run: `python scratch_login.py`
Expected: it opens Transactions, opens Custom date, fills both date fields with `20/06/2026`,
clicks Save, exports, and prints a saved CSV path under `scratch_out/`. Open the CSV and
confirm the 18-column header and that the rows are from the date you chose.

- [ ] **Step 3: Fix each selector live**

If a click/fill fails, Inspect the real element and update the matching `SEL_*` constant.
Watch especially the two date fields — if `page.fill()` doesn't stick (some masked inputs
reject it), try `page.locator(SEL_START_DATE).click()` then `page.keyboard.type("20/06/2026")`.
Re-run until a CSV for the chosen date downloads. Then delete `scratch_out/`.

- [ ] **Step 4: Commit**

```bash
git add capitec_pull/capitec_client.py
git commit -m "Add custom-date range + export-CSV flow to Capitec client"
```

---

## Task 7: Orchestrator (`pull.py`)

Ties everything together: load config, compute report date, loop branches with per-branch
isolation, save CSVs to the final names, write sidecars, print a summary, and exit non-zero
if any branch failed. The browser parts are imported from the verified client.

**Files:**
- Create: `capitec_pull/pull.py`

- [ ] **Step 1: Write the orchestrator**

```python
# capitec_pull/pull.py
"""Entry point: pull a target day's Capitec CSV for every configured branch.

Default target = yesterday (SAST). Override with --date YYYY-MM-DD.
Sundays and ZA public holidays are skipped (business closed).
"""
from __future__ import annotations
import argparse
import sys
from datetime import datetime
from pathlib import Path

from .config_loader import load_branches, ConfigError
from .dates import yesterday_sast, to_ddmmyyyy, SAST
from .workdays import is_working_day
from .naming import csv_path, sidecar_path, count_csv_rows
from .sidecar import build_sidecar, write_sidecar
from .capitec_client import browser_page, login, export_csv_for_date

CONFIG_PATH = Path(__file__).parent / "config.yaml"
PULLS_DIR = Path(__file__).parent / "pulls"
HEADLESS = False  # flip to True once the flow is proven


def pull_branch(branch, report_date: str, pulls_dir: Path) -> dict:
    """Pull one branch for report_date. Returns the sidecar dict (never raises)."""
    pulled_at = datetime.now(SAST).isoformat()
    try:
        with browser_page(headless=HEADLESS) as page:
            login(page, branch.username, branch.password)
            tmp = export_csv_for_date(page, pulls_dir, to_ddmmyyyy(report_date))

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
```

- [ ] **Step 2: Run the full pull headed against all branches**

Pre-req: `config.yaml` has all 3 branches' real credentials. Use `--date` to target a day
you know had sales (a plain run targets yesterday and is skipped if yesterday was closed).

Run:
```bash
source .venv/bin/activate
python -m capitec_pull.pull --date 2026-06-20
```
Expected: for each branch it prints `pulled (N rows)` / `no_card_sales` / `failed (...)`, and
`pulls/` contains a `<date>_<branch>.csv` and `<date>_<branch>.json` per successful branch.
Open one CSV (18-col header) and one sidecar (matches the contract) to confirm.

- [ ] **Step 3: Confirm the full unit-test suite still passes**

Run: `pytest -v`
Expected: all tests from Tasks 1–4 PASS.

- [ ] **Step 4: Commit**

```bash
git add capitec_pull/pull.py
git commit -m "Add orchestrator: per-branch pull, sidecars, run summary"
```

---

## Task 8: README & headless switch

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

````markdown
# Capitec CSV Pull

Pulls yesterday's Capitec merchant card-machine transactions (per branch) as CSV
and stages them in `capitec_pull/pulls/` for the HDM Portal "push" stage to upload.

This is the **pull** half only. The **push** half (folder → `POST /api/accounts/uploads/capitec`)
lives in the HDM_Portal repo and is built separately.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp capitec_pull/config.example.yaml capitec_pull/config.yaml
# edit capitec_pull/config.yaml with real branch credentials (gitignored)
```

## Run

```bash
source .venv/bin/activate
python -m capitec_pull.pull            # target = yesterday (SAST)
python -m capitec_pull.pull --date 2026-06-20   # catch up a specific day
```

Sundays and South African public holidays are skipped automatically (business closed).
A working day (Mon–Sat) with no card sales is recorded with status `no_card_sales`.

Outputs per branch into `capitec_pull/pulls/`:
- `<YYYY-MM-DD>_<branchCode>.csv` — raw Capitec export
- `<YYYY-MM-DD>_<branchCode>.json` — sidecar: `{branchCode, reportDate, file, status, rowCount, error, pulledAt}`
  where `status` is `pulled` | `no_card_sales` | `failed`.

`HEADLESS` in `capitec_pull/pull.py` runs the browser visibly (`False`) while building;
set to `True` for unattended runs.

## Tests

```bash
pytest -v
```
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Add README"
```

---

## Self-Review Notes

- **Spec coverage:** tooling/Playwright (T0,5,6), project layout (T0–8), config.yaml
  approach (T2), per-branch flow + login + Yesterday + export (T5,6), yesterday-in-SAST (T1),
  folder contract csv+sidecar (T3,4,7), per-branch error isolation + empty-day
  no_card_sales (T7), manual run + headless toggle (T7,8), gitignore of secrets/pulls
  (already committed). All spec sections map to a task.
- **Out of scope (unchanged):** push to portal API, scheduling, any HDM_Portal change.
- **Known unknown:** the `SEL_*` selectors in `capitec_client.py` are placeholders and are
  verified/fixed live during Tasks 5–6 — by design, not a gap.
