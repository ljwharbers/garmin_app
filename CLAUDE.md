# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A personal Garmin activity dashboard: a Python CLI pulls activity/health data from Garmin Connect into a local SQLite cache, and a Streamlit app reads that cache to render Plotly charts. Single-user, runs locally.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then fill in GARMIN_EMAIL / GARMIN_PASSWORD

# Fetch / refresh data into data/garmin.db
python -m scripts.refresh                     # incremental: since last stored activity
python -m scripts.refresh --since 2025-01-01  # from a date
python -m scripts.refresh --full              # full backfill from 2020-01-01
python -m scripts.refresh --log-level DEBUG   # INFO/WARNING/ERROR also valid

# Run the dashboard (dev and prod are the same)
streamlit run app/Home.py

# Run tests
python -m pytest
```

Run all commands from the project root. No linter or formatter is configured — do not assume `ruff`/`black` exist. `pytest` is configured (see `pytest.ini`).

## Architecture

Strict one-way data flow:

```
Garmin Connect API → fetch.py → SQLite (data/garmin.db) → db.py readers
   → transform.py / records.py (pure pandas) → Streamlit pages (app/)
```

**All network/API access is isolated in `src/garmin_reporting/fetch.py`.** Everything downstream reads only from the local SQLite DB — the Streamlit app never touches the network. Preserve this boundary: new data needs go through fetch → DB, not direct API calls from transforms or pages.

- `auth.py` — `get_client()` returns an authenticated `garminconnect.Garmin`; tokens cached in `~/.garminconnect/` (outside the repo), MFA prompted interactively on first login only.
- `db.py` — stdlib `sqlite3`, no ORM. `get_conn()` context manager (WAL + FK, auto commit/rollback). Tables: `activities` (keeps full `raw_json`), `activity_splits`, `daily_health`, `personal_records`. All writes are idempotent UPSERTs. Readers return pandas DataFrames; `get_activities_df()` converts times to `Europe/Brussels`.
- `fetch.py` — `run_fetch(since, full)` picks the start date then fetches activities/health/PRs. Uses a defensive `_safe()` getter for messy payloads and `time.sleep(API_SLEEP_S)` between detail calls. Incremental health fetches skip already-stored days except the trailing `HEALTH_REFETCH_DAYS` window (see `config.py`).
- `transform.py` — pure DataFrame→DataFrame functions, no DB/API. `enrich_activities()` (adds `distance_km`, formatted pace/duration, period columns) is called at the top of nearly every page. Also rolling load / ACWR, weekly/monthly summaries.
- `records.py` — `format_personal_records()` (displays real Garmin PRs from the `personal_records` DB table), streaks, milestones, longest/fastest activity.
- `app/Home.py` + `app/pages/N_Name.py` — Streamlit multi-page; numeric filename prefix controls sidebar order.

## Conventions & gotchas

- **The package is not pip-installed.** Every entry point (`scripts/refresh.py` and each `app/` page) prepends `src/` and the project root to `sys.path` so `import garmin_reporting...` and `import config` resolve. Replicate this hack in any new entry point. `config.py` lives at the repo root, not inside the package.
- **Tests** use `pytest.ini` with `pythonpath = src .`, so `import garmin_reporting.*` and `import config` resolve in tests without `sys.path` hacks. Run `python -m pytest` from the project root.
- Each Streamlit page follows the same template: path injection → `st.set_page_config` → `@st.cache_data(ttl=600)` loader (`get_*_df()` + `enrich_activities`) → empty-data guard (`st.info(...); st.stop()`) → sidebar filters → `plotly_dark` charts. Match it when adding pages.
- `garminconnect` is an unofficial client — pin versions; endpoints can change/break.
- `Europe/Brussels` timezone is hardcoded in `db.get_activities_df()`.
- Credentials (`.env`) and token cache (`~/.garminconnect/`) are deliberately kept out of the repo — the repo lives in a OneDrive folder, so never commit or relocate them into it. `data/` (the SQLite DB) is gitignored.
