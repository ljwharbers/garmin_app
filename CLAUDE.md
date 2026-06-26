# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A personal Garmin activity dashboard, installable as a Python package. `pip install -e .` registers two commands: `garmin-dashboard` opens a native desktop window (NiceGUI + pywebview), and `garmin-dashboard-fetch` is a headless CLI for syncing data. Login, MFA, and data fetching all happen inside the app UI — no `.env` file required.

## Commands

```bash
# Setup (one-time)
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # installs the package + dev deps (pytest)

# Launch the desktop app (opens a native window)
garmin-dashboard

# Launch in browser mode (no pywebview needed)
garmin-dashboard --browser

# Fetch / refresh data headlessly (uses cached tokens or .env fallback)
garmin-dashboard-fetch                     # incremental: since last stored activity
garmin-dashboard-fetch --since 2025-01-01  # from a date
garmin-dashboard-fetch --full              # full backfill from 2020-01-01
garmin-dashboard-fetch --log-level DEBUG

# Run tests
python -m pytest
```

Run all commands from the project root. No linter or formatter is configured — do not assume `ruff`/`black` exist.

## Architecture

Strict one-way data flow:

```
Garmin Connect API → fetch.py → SQLite (~user-data/garmin-dashboard/garmin.db)
   → db.py readers → transform.py / records.py (pure pandas)
   → NiceGUI pages (src/garmin_reporting/app/)
```

**All network/API access is isolated in `src/garmin_reporting/fetch.py`.** Everything downstream reads only from the local SQLite DB. Preserve this boundary.

### Backend modules (`src/garmin_reporting/`)

- `config.py` — **inside the package** (not at repo root). `DB_PATH` points to the OS user-data dir via `platformdirs` (`~/Library/Application Support/garmin-dashboard/garmin.db` on macOS). `TOKEN_STORE` stays at `~/.garminconnect`. Call `ensure_dirs()` before first DB access — `init_db()` does this automatically.
- `auth.py` — Three-function UI-friendly login API: `login_with_tokens()` → tries cached tokens, returns client or None; `begin_login(email, pwd)` → returns `(client, None)` or `(client, mfa_state)` for MFA accounts; `complete_login(client, state, code)` → finishes MFA. CLI fallback: `get_client()` reads `.env` and prompts for MFA interactively.
- `db.py` — stdlib `sqlite3`, no ORM. `get_conn()` context manager. Tables: `activities`, `activity_splits`, `daily_health`, `personal_records`. All writes are idempotent UPSERTs. `get_activities_df()` converts times to `Europe/Brussels`.
- `fetch.py` — `run_fetch(client=None, since=None, full=False, progress=None)` orchestrates activities/health/PRs. Accepts an optional progress callback `(phase, current, total, message)` for UI progress bars. Returns `{"activities": n, "health_days": n, "prs": n}`. If `client` is None, falls back to `get_client()`.
- `transform.py` — pure DataFrame→DataFrame functions: `enrich_activities`, `weekly_summary`, `monthly_summary`, `rolling_load`, `cumulative_distance`, `year_over_year`, `fmt_pace`, `fmt_duration`.
- `records.py` — `format_personal_records`, `longest_activity`, `fastest_pace`, `current_streak`, `longest_streak`, `distance_milestones`.
- `cli.py` — `garmin-dashboard-fetch` entry point; calls `run_fetch` with no client (falls back to `get_client()`).

### NiceGUI app (`src/garmin_reporting/app/`)

- `main.py` — `run()` entry point (registered as `garmin-dashboard`). Exports `nav_drawer()` used by every page. Attempts silent token login on startup (`@nicegui_app.on_startup`).
- `state.py` — Module-level data cache (replaces `@st.cache_data`). `get_acts()`, `get_health()`, `get_prs()`, `get_splits(activity_id)`. Call `invalidate()` after a successful fetch to clear the cache.
- `charts.py` — Pure `DataFrame → go.Figure` factory functions. All use `plotly_dark` template and the shared color palette `#00CC96/#EF553B/#AB63FA/#636EFA/#FFA15A`.
- `account.py` — `/account` page: in-UI login (MFA-aware), fetch with live progress bar and log, data status summary.
- `pages/overview.py` — `/` — KPI cards, cumulative-distance chart, recent activities table.
- `pages/trends.py` — `/trends` — Weekly/monthly distance, pace scatter, HR trend, resting HR, VO₂max, year-over-year.
- `pages/activities.py` — `/activities` — Filterable table, activity selector, split-level charts.
- `pages/records.py` — `/records` — PRs, streaks/extremes, distance milestones, all-time summary.
- `pages/training_load.py` — `/training-load` — ACWR chart + zone readout, training status/readiness, sleep.

## Conventions & gotchas

- **`config` is inside the package.** Import as `from garmin_reporting.config import X` — never `from config import X`. The root `config.py` is a legacy shim for the old Streamlit app (to be deleted in a future cleanup pass).
- **`pytest.ini` uses `pythonpath = src`** (no `.` needed — `config` is now in-package). Run `python -m pytest` from project root.
- **NiceGUI pages register via `@ui.page` at import time.** `main.py` imports all page modules to fire their decorators; do the same for any new pages.
- **Fetching is blocking/sync.** The account page runs `run_fetch` in a `threading.Thread` and polls via `ui.timer(0.2)` — do NOT call it directly from an async handler or the UI will freeze.
- **State cache is process-global.** Call `state.invalidate()` after a successful fetch so pages reload fresh data on next access.
- `garminconnect` is an unofficial client — pin versions; endpoints can change/break.
- `Europe/Brussels` timezone is hardcoded in `db.get_activities_df()`.
- **pywebview platform requirements:** Windows needs WebView2 / .NET Framework; Linux needs a GTK or Qt webview package. Use `--browser` flag as a fallback on any platform.
- Credentials (`.env`) and token cache (`~/.garminconnect/`) are kept out of the repo — the repo lives in a OneDrive folder, so never commit or relocate them. The DB (`~/Library/Application Support/garmin-dashboard/garmin.db` on macOS) is outside the repo and never synced.
