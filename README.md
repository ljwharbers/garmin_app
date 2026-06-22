# Garmin Activity Dashboard

An interactive Streamlit dashboard for training and performance analytics,
built on top of a local SQLite cache populated via the `garminconnect` Python
library.

## Quick start

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up credentials
cp .env.example .env
# Edit .env and add your Garmin Connect email + password

# 4. Fetch your data (first run will prompt for login / MFA)
python -m scripts.refresh

# To fetch everything from 2020 onwards:
# python -m scripts.refresh --full

# 5. Run the dashboard
streamlit run app/Home.py
```

## Project structure

```
garmin_reporting/
├── .env                     # Your credentials (gitignored)
├── .env.example             # Template — copy to .env
├── requirements.txt
├── config.py                # Paths, defaults, settings
├── data/
│   └── garmin.db            # Local SQLite cache (gitignored)
├── src/garmin_reporting/
│   ├── auth.py              # Login + token cache
│   ├── db.py                # Schema + read/write helpers
│   ├── fetch.py             # Garmin → SQLite (incremental)
│   ├── transform.py         # Derived metrics (pure functions)
│   └── records.py           # PRs, streaks, milestones
├── scripts/
│   └── refresh.py           # CLI: python -m scripts.refresh
└── app/
    ├── Home.py              # Overview page
    └── pages/
        ├── 1_Trends.py
        ├── 2_Activities.py
        ├── 3_Records.py
        └── 4_Training_Load.py
```

## Refreshing data

```bash
# Incremental (default — fetches since last stored activity):
python -m scripts.refresh

# From a specific date:
python -m scripts.refresh --since 2025-01-01

# Full backfill:
python -m scripts.refresh --full
```

## Notes

- This uses the **unofficial** `garminconnect` library (community-maintained).
  Pin your version in `requirements.txt` — Garmin can change endpoints.
- Credentials live in `.env`, token cache in `~/.garminconnect/` — both outside
  the repo and never synced to the cloud.
- MFA: if enabled on your account, the first login will prompt for a one-time
  code. Subsequent runs reuse cached tokens automatically.
