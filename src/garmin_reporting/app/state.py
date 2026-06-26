"""
Data-cache layer for the NiceGUI desktop app.

Replaces @st.cache_data from the previous Streamlit implementation. Data is
loaded lazily on first access and stored in a module-level dict. Call
invalidate() after a successful Garmin fetch so the next access reloads fresh
data from the database.
"""

import logging

import pandas as pd

from garmin_reporting.db import (
    get_activities_df,
    get_daily_health_df,
    get_personal_records_df,
    get_splits_df,
)
from garmin_reporting.transform import enrich_activities

logger = logging.getLogger(__name__)

# Process-global cache — single-user assumption (see account.py for the same note).
_cache: dict = {"acts": None, "health": None, "prs": None}


def get_acts() -> pd.DataFrame:
    """Return the enriched activities DataFrame, loading from the DB if needed."""
    if _cache["acts"] is None:
        try:
            df = get_activities_df()
            if not df.empty:
                df = enrich_activities(df)
            _cache["acts"] = df
        except Exception:
            logger.exception("Failed to load activities")
            return pd.DataFrame()
    return _cache["acts"]


def get_health() -> pd.DataFrame:
    """Return the daily health DataFrame, loading from the DB if needed."""
    if _cache["health"] is None:
        try:
            _cache["health"] = get_daily_health_df()
        except Exception:
            logger.exception("Failed to load daily health data")
            return pd.DataFrame()
    return _cache["health"]


def get_prs() -> pd.DataFrame:
    """Return the personal records DataFrame, loading from the DB if needed."""
    if _cache["prs"] is None:
        try:
            _cache["prs"] = get_personal_records_df()
        except Exception:
            logger.exception("Failed to load personal records")
            return pd.DataFrame()
    return _cache["prs"]


def get_splits(activity_id: str) -> pd.DataFrame:
    """Return splits for a single activity. Not cached at module level."""
    try:
        return get_splits_df(activity_id)
    except Exception:
        logger.exception("Failed to load splits for activity %s", activity_id)
        return pd.DataFrame()


def invalidate() -> None:
    """Clear all cached DataFrames so the next access reloads from the DB."""
    _cache["acts"] = None
    _cache["health"] = None
    _cache["prs"] = None
