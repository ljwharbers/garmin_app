"""Central configuration: paths, defaults, and settings."""
from pathlib import Path

# ---- Project root --------------------------------------------------------
ROOT = Path(__file__).parent

# ---- Data / cache --------------------------------------------------------
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "garmin.db"

# ---- Token cache (outside the repo — never synced/committed) -------------
TOKEN_STORE = Path.home() / ".garminconnect"

# ---- Fetch defaults ------------------------------------------------------
# How far back to go on a first-ever fetch (full backfill).
# Override with --since on the CLI.
DEFAULT_BACKFILL_DATE = "2020-01-01"

# Seconds to sleep between individual activity-detail API calls.
API_SLEEP_S = 0.5

# Number of activities to request per page when listing.
ACTIVITIES_BATCH = 100
