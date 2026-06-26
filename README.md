# Garmin Activity Dashboard

A personal Garmin Connect activity dashboard — installable Python app with a native desktop window.
Log in, sync your data, and explore training analytics: trends, activities, records, ACWR load, and health metrics.

## Installation

```bash
pip install garmin-dashboard
# or, for development from this repo:
git clone <repo>
cd garmin_reporting
pip install -e ".[dev]"
```

**Platform requirements for the native window:**
- macOS: works out of the box (WKWebView)
- Windows: requires [WebView2 runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) (usually pre-installed on Windows 11)
- Linux: requires a system GTK/Qt webview package (e.g. `python3-gi` + `gir1.2-webkit2-4.0` on Ubuntu)
- Use `garmin-dashboard --browser` on any platform to open in your default browser instead

## Quick start

```bash
# 1. Launch the app
garmin-dashboard

# 2. A window opens — go to "Data & Account" in the sidebar
# 3. Enter your Garmin Connect email + password → log in
#    (If MFA is enabled, a code field appears)
# 4. Click "Fetch now" to sync your data
# 5. Browse your activities in the other pages
```

That's it. No `.env` file, no terminal credential setup. Your password is never saved — only the session tokens (cached in `~/.garminconnect/`, valid ~1 year) are kept.

## Headless / CLI usage

If you prefer to sync data from the terminal (e.g. in a cron job), use the fetch CLI:

```bash
# Incremental (since last stored activity):
garmin-dashboard-fetch

# From a specific date:
garmin-dashboard-fetch --since 2025-01-01

# Full backfill from 2020:
garmin-dashboard-fetch --full

# With verbose logging:
garmin-dashboard-fetch --log-level DEBUG
```

The CLI looks for cached tokens from a previous in-app login. As a fallback it reads `GARMIN_EMAIL` / `GARMIN_PASSWORD` from a `.env` file in the current directory.

## Project structure

```
garmin_reporting/
├── pyproject.toml               # Package metadata + entry points
├── src/garmin_reporting/
│   ├── config.py                # Paths, defaults (DB in OS user-data dir)
│   ├── auth.py                  # Login: token-first, two-step MFA support
│   ├── db.py                    # SQLite schema + read/write helpers
│   ├── fetch.py                 # Garmin API → SQLite (incremental, with progress)
│   ├── transform.py             # Derived metrics (pure pandas functions)
│   ├── records.py               # PRs, streaks, milestones
│   ├── cli.py                   # garmin-dashboard-fetch entry point
│   └── app/
│       ├── main.py              # garmin-dashboard entry point + nav_drawer
│       ├── state.py             # Data cache (replaces @st.cache_data)
│       ├── charts.py            # Plotly figure factories (all plotly_dark)
│       ├── account.py           # /account — login + fetch with progress bar
│       └── pages/
│           ├── overview.py      # / — KPIs, cumulative distance, recent activities
│           ├── trends.py        # /trends — weekly/monthly charts, pace, HR, YoY
│           ├── activities.py    # /activities — filterable table + split detail
│           ├── records.py       # /records — PRs, streaks, milestones, all-time
│           └── training_load.py # /training-load — ACWR, readiness, sleep
├── tests/                       # pytest suite
└── requirements.txt             # Legacy (use pip install -e . instead)
```

## Data storage

- **Database:** `~/Library/Application Support/garmin-dashboard/garmin.db` (macOS) — outside the repo, never synced.
- **Tokens:** `~/.garminconnect/` — the garminconnect default, outside the repo.
- **Credentials:** never stored — typed once per login, then only tokens are kept.

## Notes

- Uses the **unofficial** `garminconnect` library (community-maintained). Pin your version — Garmin can change endpoints without notice.
- `Europe/Brussels` timezone is hardcoded in `db.get_activities_df()`. Change `DB_TZ` in `config.py` if needed.
- MFA is handled fully in-app: log in, a code field appears, enter the code — done.
