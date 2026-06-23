# Capitec CSV Pull

Pulls a day's Capitec merchant card-machine transactions (per branch) as CSV
and stages them in `capitec_pull/pulls/` for the HDM Portal "push" stage to upload.

This is the **pull** half only. The **push** half (folder ->
`POST /api/accounts/uploads/capitec`) lives in the HDM_Portal repo and is built
separately.

## Setup

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    playwright install chromium
    cp capitec_pull/config.example.yaml capitec_pull/config.yaml
    # edit capitec_pull/config.yaml with real branch credentials (gitignored)

## Run

    python -m capitec_pull.pull                      # target = yesterday (SAST)
    python -m capitec_pull.pull --date 2026-06-20    # catch up a specific day

Sundays and South African public holidays are skipped automatically. A working
day (Mon-Sat) with no card sales is recorded with status `no_card_sales`.

Outputs per branch into `capitec_pull/pulls/`:
- `<YYYY-MM-DD>_<branchCode>.csv` -- the raw Capitec export
- `<YYYY-MM-DD>_<branchCode>.json` -- sidecar:
  `{branchCode, reportDate, file, status, rowCount, error, pulledAt}`
  where `status` is `pulled` | `no_card_sales` | `failed`.

`HEADLESS` in `capitec_pull/pull.py` runs the browser visibly while building;
set to `True` for unattended runs.

## Tests

    pytest -v
