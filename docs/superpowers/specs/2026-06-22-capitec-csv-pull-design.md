# Capitec CSV Pull — Design

**Date:** 2026-06-22
**Status:** Approved (design)
**Scope:** The "pull" stage only — extract yesterday's card-machine transactions from
the Capitec merchant portal as CSV and stage them in a folder for a separate "push"
stage to upload into the HDM Portal.

---

## 1. Background & Goal

HDM operates a reconciliation portal (`HDM_Portal`, database `hdm_portal`) where, today,
a human logs in and **manually uploads** a Capitec card-machine CSV per branch per day.
The portal parses it and writes `capitec_reports` + `capitec_transactions` rows, dedupes,
and auto-reconciles.

**End goal:** users stop uploading manually. An automated job pulls the CSVs from Capitec
and feeds them to the portal.

This project is split into two independently-built stages that meet at a **folder
contract**:

1. **Pull (this spec, this session):** Capitec portal → CSV files in a folder.
2. **Push (separate session, in the `HDM_Portal` repo):** folder → portal API.

The folder is the only interface between them.

## 2. Key Decision — Reuse the Portal API (do NOT touch the DB)

The portal's Python backend (`backend-py`) already contains all ingest logic, exposed as:

```
POST /api/accounts/uploads/capitec
  file:       <the CSV>            (multipart)
  branchCode: <"101" | "202" | "303">
  reportDate: <YYYY-MM-DD>
  Authorization: Bearer <JWT from POST /api/auth/login>
```

This endpoint parses, inserts `capitec_reports` + `capitec_transactions`, guards against
duplicates (HTTP 409 on existing `branch_code` + `report_date`), and auto-reconciles.
There is also `POST /api/accounts/uploads/capitec/no-card-sales` for empty days.

The pull stage therefore writes **no database code and no CSV-parsing code**. It only does
the part the portal cannot: get the file out of Capitec. The push stage hands each file to
the endpoint above exactly as the browser does today.

Relevant portal source (for the push session's reference):
- `backend-py/app/routers/accounts_uploads.py` — upload endpoints
- `backend-py/app/recon/capitec_parser.py` — CSV/XLSX parser
- `backend-py/app/routers/accounts_uploads_helpers.py` — `ingest_capitec`
- `backend-py/app/routers/auth.py` — `POST /api/auth/login`

## 3. Inputs

- **Site:** `https://merchant.capitecbank.co.za/app/login` (same site for all branches).
- **Login:** username + password only — **no OTP / no app approval** (confirmed).
- **Branches:** 3, each with its own Capitec credentials, mapped to a portal `branchCode`:
  - `101`, `202`, `303`
- **Manual flow being automated:** sign in → Transactions → change "Today" to "Yesterday"
  → Export → CSV.

## 4. CSV Shape (reference)

18-column header, comma-separated:

```
Merchant ID, Trading Name, Card Number, Payment Channel, Date And Time, Status,
Device ID, Transaction Total, Sale Amount, Tip Amount, Cash Amount, Currency Code,
Transaction Description, RRN, Note, Staff Number, Card, Transaction ID
```

Notes: `Date And Time` is `DD/MM/YYYY HH:MM:SS`; amounts can be negative (refunds);
`Status` can be `Approved` or `Declined`. The pull stage does **not** parse or modify the
CSV — it saves the raw export untouched.

## 5. Architecture

```
capitec_pull/
  config.example.yaml   committed template
  config.yaml           real branch credentials — GITIGNORED, never committed
  dates.py              yesterday-in-SAST + DD/MM/YYYY formatting (pure)
  workdays.py           working-day check (skip Sundays + ZA public holidays) (pure)
  config_loader.py      load + validate config.yaml (pure)
  naming.py             filenames + CSV row count (pure)
  sidecar.py            build + write sidecar JSON
  capitec_client.py     Playwright automation: login, custom-date range, export CSV
  pull.py               entry point: parse --date, skip non-working days, loop branches
  pulls/                output folder — GITIGNORED
requirements.txt
.gitignore
```

- **Tooling:** Playwright (Python). Chosen over Selenium for auto-waiting (the portal is a
  JS SPA), built-in download handling, and easy headed/headless toggle. Run **headed**
  while building, switch to headless once stable.
- **`capitec_client.py`** — one clear job: given a branch's credentials, drive the browser
  and return the path to the downloaded CSV (or raise on failure). Knows nothing about the
  folder contract or config format.
- **`pull.py`** — orchestrates: load config, compute `reportDate`, loop branches, call the
  client, write outputs and sidecars, aggregate a run summary.

## 6. Config (`config.yaml`, gitignored)

```yaml
branches:
  - branch_code: "101"
    username: "..."
    password: "..."
  - branch_code: "202"
    username: "..."
    password: "..."
  - branch_code: "303"
    username: "..."
    password: "..."
```

`config.example.yaml` carries the same structure with placeholder values and is committed.

## 7. Output / Folder Contract

For each branch, into `pulls/`:

- `pulls/<reportDate>_<branchCode>.csv` — the raw Capitec export, byte-for-byte.
- `pulls/<reportDate>_<branchCode>.json` — sidecar:

```json
{
  "branchCode": "101",
  "reportDate": "2026-06-22",
  "file": "2026-06-22_101.csv",
  "status": "pulled",          // "pulled" | "no_card_sales" | "failed"
  "rowCount": 54,               // best-effort line count, optional
  "error": null,                // populated when status == "failed"
  "pulledAt": "2026-06-22T05:10:00+02:00"
}
```

The push session watches this folder, reads the sidecar, and POSTs accordingly
(`status: "no_card_sales"` → the no-card-sales endpoint).

## 8. Target Date & Working-Day Logic

The script pulls **one target date** per run:

- **Default target = yesterday** in **SAST** (UTC+2, fixed), formatted `YYYY-MM-DD`. Used for
  the filename and the portal `reportDate`.
- **`--date YYYY-MM-DD` override** pulls a specific earlier day (catch-up after a gap).
- **Working days are Mon–Sat.** If the target date is a **Sunday or a South African public
  holiday**, the run **skips entirely** (no browser, no report) and exits 0 — the business
  was closed, so there is nothing to pull.
- A normal working day (Mon–Sat) with genuinely zero card sales is **not** skipped — it is
  recorded as `status: "no_card_sales"` (open but no card transactions).

Public holidays come from the **`holidays` Python library** (South Africa), which handles
the Sunday-rollover rule. No manually maintained list.

**Known limitation (accepted for v1):** the "pull yesterday, skip closed days" model assumes
the script runs every day. It does **not** auto-backfill a long gap (e.g. machine off for a
week); use `--date` per missed day, or add a backfill feature later if needed (YAGNI).

### Capitec date-range UI (observed on the live site)

The Transactions page has a date-range button (top-right) that opens a menu: Today,
Yesterday, Last 7 days, Last 30 days, Custom date. **Custom date** reveals two typeable
text fields — **Start date** and **End date** (format `DD/MM/YYYY`) — and a **Save** button
("date range up to 6 months"). The script uses Custom date for **every** pull (uniform, and
provably matches the computed date), setting **Start = End = target** in `DD/MM/YYYY`, then
Save, then **Export → CSV**. (The "Yesterday" shortcut is deliberately not used — explicit
date beats relying on Capitec's notion of "yesterday".)

## 9. Error Handling

- Each branch runs independently. A failure (bad login, changed page, missing Export) is
  logged, written to the sidecar as `status: "failed"` with an `error` reason, and the run
  **continues to the next branch**.
- An empty export (no transactions yesterday) is a normal outcome, recorded as
  `status: "no_card_sales"` — not an error.
- `pull.py` exits non-zero if any branch failed, so a future scheduler can alert.

## 10. Running

- Now: manual — `python pull.py`.
- Later (separate, out of scope here): schedule daily via macOS `launchd`.

## 11. Known Unknown — Selectors

The actual login form fields, the Transactions navigation, the Today→Yesterday control,
and the Export→CSV flow are not yet known (JS SPA). They must be discovered against the
**live** site. Build is therefore iterative: scaffold structure first, then run headed
against the real portal and adjust selectors from what we observe. This is expected for
browser automation and is not a design gap.

## 12. Security Notes

- Real credentials live only in `config.yaml`, which is gitignored. Never committed, never
  pasted into chat.
- `pulls/` (which contains card transaction data) is gitignored.
- The portal DB currently uses Postgres `trust` auth with no password — out of scope here,
  but worth revisiting on the portal side if the network is not fully locked down.

## 13. Out of Scope

- Uploading to the portal API (push stage — separate session).
- Scheduling.
- Any change to the HDM Portal codebase or database.
