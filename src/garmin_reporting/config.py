"""Central configuration: paths, defaults, and settings.

When installed as a package the database lives in the OS user-data directory
(e.g. ~/Library/Application Support/garmin-dashboard/ on macOS) rather than
inside the repository, so data persists across reinstalls and is never
accidentally committed.

Call ensure_dirs() before opening the database for the first time (init_db()
does this automatically).
"""
from pathlib import Path

import platformdirs

# ---- Data / cache ------------------------------------------------------------
# User-facing app name used for the OS data directory.
_APP_NAME = "garmin-dashboard"

DATA_DIR: Path = Path(platformdirs.user_data_dir(_APP_NAME, appauthor=False))
DB_PATH: Path = DATA_DIR / "garmin.db"

# ---- Token cache (garminconnect default — outside the repo) ------------------
TOKEN_STORE: Path = Path.home() / ".garminconnect"

# ---- Fetch defaults ----------------------------------------------------------
# How far back to go on a first-ever fetch (full backfill).
# Override with --since on the CLI.
DEFAULT_BACKFILL_DATE: str = "2020-01-01"

# Seconds to sleep between individual activity-detail API calls.
API_SLEEP_S: float = 0.5

# Number of activities to request per page when listing.
ACTIVITIES_BATCH: int = 100

# Days to re-fetch even if already stored (metrics like sleep/readiness finalize late).
HEALTH_REFETCH_DAYS: int = 3


def ensure_dirs() -> None:
    """Create the data directory if it does not yet exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
