"""Derived metrics computed from the local SQLite data.

All functions take a pandas DataFrame (from db.get_activities_df or
db.get_daily_health_df) and return a new DataFrame or Series.
These are pure: no DB calls, no API calls.
"""
from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Pace formatting
# ---------------------------------------------------------------------------

def fmt_pace(seconds_per_km: float | None) -> str:
    """Format pace as 'M:SS /km'.  Returns '' if None or invalid."""
    if seconds_per_km is None or pd.isna(seconds_per_km) or seconds_per_km <= 0:
        return ""
    total = int(round(seconds_per_km))
    mins, secs = divmod(total, 60)
    return f"{mins}:{secs:02d}"


def fmt_duration(seconds: float | None) -> str:
    """Format duration as 'H:MM:SS' or 'M:SS' if < 1 hour."""
    if seconds is None or pd.isna(seconds):
        return ""
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Activity-level enrichment
# ---------------------------------------------------------------------------

def enrich_activities(df: pd.DataFrame) -> pd.DataFrame:
    """Add human-readable columns to an activities DataFrame."""
    df = df.copy()
    df["distance_km"] = df["distance_m"] / 1000
    df["pace_fmt"] = df["avg_pace_s_per_km"].apply(fmt_pace)
    df["duration_fmt"] = df["duration_s"].apply(fmt_duration)
    df["date"] = pd.to_datetime(df["start_time"]).dt.date
    df["week"] = pd.to_datetime(df["start_time"]).dt.to_period("W").dt.start_time
    df["month"] = pd.to_datetime(df["start_time"]).dt.to_period("M").dt.start_time
    df["year"] = pd.to_datetime(df["start_time"]).dt.year
    return df


# ---------------------------------------------------------------------------
# Weekly / monthly aggregates
# ---------------------------------------------------------------------------

def weekly_summary(df: pd.DataFrame, activity_type: str | None = None) -> pd.DataFrame:
    """Return weekly totals (distance_km, duration_s, n_activities, avg_pace, avg_hr)."""
    d = enrich_activities(df)
    if activity_type:
        d = d[d["activity_type"] == activity_type]
    agg = (
        d.groupby("week")
        .agg(
            distance_km=("distance_km", "sum"),
            duration_s=("duration_s", "sum"),
            n_activities=("activity_id", "count"),
            avg_hr=("avg_hr", "mean"),
            avg_pace_s_per_km=("avg_pace_s_per_km", "mean"),
        )
        .reset_index()
        .sort_values("week")
    )
    agg["pace_fmt"] = agg["avg_pace_s_per_km"].apply(fmt_pace)
    return agg


def monthly_summary(df: pd.DataFrame, activity_type: str | None = None) -> pd.DataFrame:
    """Return monthly totals."""
    d = enrich_activities(df)
    if activity_type:
        d = d[d["activity_type"] == activity_type]
    agg = (
        d.groupby("month")
        .agg(
            distance_km=("distance_km", "sum"),
            duration_s=("duration_s", "sum"),
            n_activities=("activity_id", "count"),
            avg_hr=("avg_hr", "mean"),
            avg_pace_s_per_km=("avg_pace_s_per_km", "mean"),
        )
        .reset_index()
        .sort_values("month")
    )
    agg["pace_fmt"] = agg["avg_pace_s_per_km"].apply(fmt_pace)
    return agg


# ---------------------------------------------------------------------------
# Training load (ACWR proxy)
# ---------------------------------------------------------------------------

def rolling_load(df: pd.DataFrame, activity_type: str | None = None) -> pd.DataFrame:
    """Compute daily acute (7-day) and chronic (28-day) training loads.

    Uses distance_km as the load unit.  Returns a DataFrame indexed by date
    with columns: distance_km, acute_load, chronic_load, acwr.
    """
    d = enrich_activities(df)
    if activity_type:
        d = d[d["activity_type"] == activity_type]

    daily = (
        d.groupby("date")["distance_km"]
        .sum()
        .reset_index()
        .rename(columns={"distance_km": "distance_km"})
    )
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.set_index("date").sort_index()

    # Fill missing days with 0
    if not daily.empty:
        full_range = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
        daily = daily.reindex(full_range, fill_value=0)

    daily["acute_load"] = daily["distance_km"].rolling(7, min_periods=1).sum()
    daily["chronic_load"] = daily["distance_km"].rolling(28, min_periods=1).sum() / 4  # weekly avg
    daily["acwr"] = (daily["acute_load"] / daily["chronic_load"]).replace([float("inf")], None)
    return daily.reset_index().rename(columns={"index": "date"})


# ---------------------------------------------------------------------------
# Cumulative distance
# ---------------------------------------------------------------------------

def cumulative_distance(df: pd.DataFrame, activity_type: str | None = None) -> pd.DataFrame:
    """Return cumulative km by date (for 'distance banked' charts)."""
    d = enrich_activities(df)
    if activity_type:
        d = d[d["activity_type"] == activity_type]
    daily = (
        d.groupby("date")["distance_km"]
        .sum()
        .reset_index()
        .sort_values("date")
    )
    daily["date"] = pd.to_datetime(daily["date"])
    daily["cumulative_km"] = daily["distance_km"].cumsum()
    return daily


# ---------------------------------------------------------------------------
# Year-over-year
# ---------------------------------------------------------------------------

def year_over_year(df: pd.DataFrame, activity_type: str | None = None) -> pd.DataFrame:
    """Return weekly cumulative distance per year for YoY comparison charts."""
    d = enrich_activities(df)
    if activity_type:
        d = d[d["activity_type"] == activity_type]
    d["week_of_year"] = pd.to_datetime(d["start_time"]).dt.isocalendar().week.astype(int)
    agg = (
        d.groupby(["year", "week_of_year"])["distance_km"]
        .sum()
        .reset_index()
        .sort_values(["year", "week_of_year"])
    )
    agg["cumulative_km"] = agg.groupby("year")["distance_km"].cumsum()
    return agg


# ---------------------------------------------------------------------------
# HR zone aggregation (from daily_health)
# ---------------------------------------------------------------------------

def hr_zone_totals(health_df: pd.DataFrame) -> pd.DataFrame:
    """Return total time (hours) per HR zone across the provided health data."""
    zone_cols = [f"hr_zone{z}_s" for z in range(1, 6)]
    totals = health_df[zone_cols].sum()
    result = pd.DataFrame(
        {"zone": [f"Zone {z}" for z in range(1, 6)], "hours": (totals.values / 3600)}
    )
    return result
