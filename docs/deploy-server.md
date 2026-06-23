# Server Deployment Guide — Capitec CSV Pull (macOS / Mac mini)

This guide is for a fresh Claude session running **on the Mac mini server**. It assumes no
prior context. Read it fully before acting, and confirm the items under "Confirm with the
operator" below.

## What this project is

`capitec-auto-pull` automates the **pull** half of a two-stage pipeline:

1. **Pull (THIS repo):** logs into the Capitec merchant portal
   (`https://merchant.capitecbank.co.za/app/login`) for each of 3 branches, exports a single
   day's card-machine transactions as CSV, and writes them to `capitec_pull/pulls/`.
2. **Push (separate, NOT here):** another job reads `capitec_pull/pulls/` and POSTs each CSV
   to the HDM Portal API. Out of scope for this guide.

Default target day = **yesterday** in SAST (date logic uses a fixed UTC+2 offset, so the data
date is correct regardless of the machine's timezone). Sundays and South African public
holidays are skipped automatically. Full design: `docs/superpowers/specs/` and `.../plans/`.

### Output folder contract (what the push side consumes)

Per branch, into `capitec_pull/pulls/`:
- `<YYYY-MM-DD>_<branchCode>.csv` — raw Capitec export
- `<YYYY-MM-DD>_<branchCode>.json` — sidecar:
  `{branchCode, reportDate, file, status, rowCount, error, pulledAt}`,
  `status` is `pulled` | `no_card_sales` | `failed`.

Branch codes: `101`, `202`, `303`.

## Step 1 — clone and create the Python environment

Clone wherever you keep services (the path is referenced later as `$APP_DIR`):

```bash
git clone https://github.com/HDMAuto/capitec-auto-pull.git
cd capitec-auto-pull
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium      # macOS needs no extra OS deps
mkdir -p logs
```

## Step 2 — supply real credentials (NOT in git)

`config.yaml` holds the 3 branches' real Capitec logins and is **gitignored** — not in the
repo, must be created here. Ask the operator for the real usernames/passwords; do not invent
them.

```bash
cp capitec_pull/config.example.yaml capitec_pull/config.yaml
# edit capitec_pull/config.yaml — replace REPLACE_ME with the real
# username/password for branch_code 101, 202, 303.
chmod 600 capitec_pull/config.yaml
```

## Step 3 — verify with one manual run (headless)

Run for a recent weekday you expect had sales (replace the date):

```bash
CAPITEC_HEADLESS=1 python -m capitec_pull.pull --date 2026-06-22
ls -la capitec_pull/pulls/
cat capitec_pull/pulls/2026-06-22_101.json
```

Expect `pulled` / `no_card_sales` per branch with matching CSV + sidecar files. If a branch
shows `failed`, read the sidecar's `error` (common causes: wrong credentials, no outbound
network to `merchant.capitecbank.co.za`). `CAPITEC_HEADLESS=1` is required on a server (no
visible display needed). A plain `python -m capitec_pull.pull` (no `--date`) targets yesterday
— that is the scheduled command.

## Step 4 — install the launchd job (daily 05:00)

The repo ships `deploy/com.hdm.capitec-pull.plist`, but its paths are hardcoded to the
original dev machine (`/Users/clivefigueira/CapitecCardPull`). Regenerate it with THIS
server's clone path and install it. Run from inside the repo (so `$(pwd)` is the app dir):

```bash
APP_DIR="$(pwd)"
mkdir -p ~/Library/LaunchAgents
sed "s#/Users/clivefigueira/CapitecCardPull#$APP_DIR#g" \
    deploy/com.hdm.capitec-pull.plist > ~/Library/LaunchAgents/com.hdm.capitec-pull.plist
plutil -lint ~/Library/LaunchAgents/com.hdm.capitec-pull.plist   # expect: OK
```

The plist runs `$APP_DIR/.venv/bin/python -m capitec_pull.pull` at **05:00 daily** with
`CAPITEC_HEADLESS=1`, logging to `$APP_DIR/logs/pull.out.log` and `pull.err.log`. Load it:

```bash
U=$(id -u)
launchctl bootout gui/$U/com.hdm.capitec-pull 2>/dev/null    # ignore error if not loaded
launchctl bootstrap gui/$U ~/Library/LaunchAgents/com.hdm.capitec-pull.plist
launchctl enable gui/$U/com.hdm.capitec-pull
launchctl kickstart -k gui/$U/com.hdm.capitec-pull           # one-time test run now
sleep 60
cat logs/pull.out.log        # expect: Done. N ok, 0 failed.
cat logs/pull.err.log        # expect: empty
```

## Step 5 — make it survive reboots (IMPORTANT for a Mac mini server)

`launchd` *user agents* only run while the user is logged into a GUI session. On an unattended
Mac mini you must therefore:

1. **Enable automatic login** for this user: System Settings → Users & Groups → Automatically
   log in as → this user. (So after a power cut/reboot the session — and the agent — come back.)
2. **Prevent sleep** so it's awake at 05:00: System Settings → Displays → (Energy) → "Prevent
   automatic sleeping when the display is off", or run `sudo pmset -a sleep 0`. (`launchd` with
   a calendar interval will run a missed job shortly after wake, but staying awake is simplest.)
3. Confirm the machine's **timezone is Africa/Johannesburg** so 05:00 local = 05:00 SAST
   (`sudo systemsetup -gettimezone`). The data date is always SAST regardless, but the trigger
   time follows the system clock.

## Useful commands

- Run now (catch-up): `python -m capitec_pull.pull --date 2026-06-21`
- Trigger the scheduled job now: `launchctl kickstart -k gui/$(id -u)/com.hdm.capitec-pull`
- Check this morning's run: `cat logs/pull.out.log` (and `logs/pull.err.log`)
- Disable the schedule: `launchctl bootout gui/$(id -u)/com.hdm.capitec-pull`
- Re-enable: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.hdm.capitec-pull.plist`

## Confirm with the operator

1. Clone path / user on the Mac mini (the plist paths are regenerated from it in Step 4).
2. Real Capitec credentials for branches 101/202/303 (for `config.yaml`).
3. Automatic login + no-sleep are enabled (Step 5) — required for an unattended server.
4. Timezone is Africa/Johannesburg.
5. Whether the **push** stage will also run on this Mac mini (separate setup).
6. Outbound network to `merchant.capitecbank.co.za` is allowed.
