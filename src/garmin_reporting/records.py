"""Compute personal records, streaks, and milestones from local activity data.

These are derived from the activities DataFrame — no API calls required.
"""
from __future__ import annotations

import pandas as pd

from garmin_reporting.transform import enrich_activities, fmt_pace, fmt_duration

# Distance thresholds used for "best effort" PR computation (metres).
PR_DISTANCES = {
    "5k": 5_000,
    "10k": 10_000,
    "half_marathon": 21_097,
    "marathon": 42_195,
}


def best_efforts(df: pd.DataFrame, activity_type: str = "running") -> pd.DataFrame:
    """Return a DataFrame of best-effort times for standard race distances.

    Strategy: for each activity that is >= the target distance, compute an
    estimated time for that distance using the average pace.  This is a proxy
    — not segment-exact — but works well without downloading raw GPS tracks.
    """
    d = enrich_activities(df)
    d = d[d["activity_type"] == activity_type].copy()
    d = d.dropna(subset=["avg_pace_s_per_km", "distance_m"])

    rows = []
    for label, target_m in PR_DISTANCES.items():
        eligible = d[d["distance_m"] >= target_m].copy()
        if eligible.empty:
            rows.append({"distance": label, "best_time_s": None, "best_time_fmt": "—",
                         "pace_fmt": "—", "date": None, "activity_id": None})
            continue
        eligible["est_time_s"] = eligible["avg_pace_s_per_km"] * (target_m / 1000)
        best = eligible.loc[eligible["est_time_s"].idxmin()]
        rows.append({
            "distance": label,
            "best_time_s": best["est_time_s"],
            "best_time_fmt": fmt_duration(best["est_time_s"]),
            "pace_fmt": fmt_pace(best["avg_pace_s_per_km"]),
            "date": str(best["date"]),
            "activity_id": best["activity_id"],
        })
    return pd.DataFrame(rows)


def longest_activity(df: pd.DataFrame, activity_type: str = "running") -> dict:
    """Return the single longest activity (by distance) as a dict."""
    d = enrich_activities(df)
    d = d[d["activity_type"] == activity_type].dropna(subset=["distance_m"])
    if d.empty:
        return {}
    row = d.loc[d["distance_m"].idxmax()]
    return {
        "distance_km": round(row["distance_km"], 2),
        "duration_fmt": row["duration_fmt"],
        "pace_fmt": row["pace_fmt"],
        "date": str(row["date"]),
        "activity_id": row["activity_id"],
    }


def fastest_pace(df: pd.DataFrame, activity_type: str = "running", min_km: float = 1.0) -> dict:
    """Return the activity with the fastest average pace (min distance filter)."""
    d = enrich_activities(df)
    d = d[d["activity_type"] == activity_type]
    d = d[d["distance_km"] >= min_km].dropna(subset=["avg_pace_s_per_km"])
    if d.empty:
        return {}
    row = d.loc[d["avg_pace_s_per_km"].idxmin()]
    return {
        "pace_fmt": row["pace_fmt"],
        "distance_km": round(row["distance_km"], 2),
        "date": str(row["date"]),
        "activity_id": row["activity_id"],
    }


def current_streak(df: pd.DataFrame, activity_type: str | None = None) -> int:
    """Return the number of consecutive days (ending today or yesterday) with an activity."""
    d = enrich_activities(df)
    if activity_type:
        d = d[d["activity_type"] == activity_type]
    if d.empty:
        return 0

    active_days = set(d["date"].astype(str))
    today = pd.Timestamp.today().date()
    streak = 0
    check = today
    while str(check) in active_days:
        streak += 1
        check = (pd.Timestamp(check) - pd.Timedelta(days=1)).date()
    # Also try starting from yesterday (so streak doesn't break mid-day).
    if streak == 0:
        check = (pd.Timestamp(today) - pd.Timedelta(days=1)).date()
        while str(check) in active_days:
            streak += 1
            check = (pd.Timestamp(check) - pd.Timedelta(days=1)).date()
    return streak


def longest_streak(df: pd.DataFrame, activity_type: str | None = None) -> int:
    """Return the all-time longest consecutive-day activity streak."""
    d = enrich_activities(df)
    if activity_type:
        d = d[d["activity_type"] == activity_type]
    if d.empty:
        return 0

    dates = sorted(set(pd.to_datetime(d["date"]).dt.date))
    if not dates:
        return 0

    best = 1
    cur = 1
    for i in range(1, len(dates)):
        delta = (dates[i] - dates[i - 1]).days
        if delta == 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def distance_milestones(df: pd.DataFrame, activity_type: str | None = "running",
                         step_km: int = 500) -> list[dict]:
    """Return a list of milestones (how many 'step_km' chunks have been completed)."""
    d = enrich_activities(df)
    if activity_type:
        d = d[d["activity_type"] == activity_type]
    total_km = d["distance_km"].sum()

    milestones = []
    km = step_km
    while km <= total_km:
        # Find the date this milestone was crossed.
        cumsum = d.sort_values("start_time")["distance_km"].cumsum()
        idx = (cumsum >= km).idxmax()
        crossed_date = str(d.loc[idx, "date"]) if not cumsum.empty else None
        milestones.append({"milestone_km": km, "date_reached": crossed_date})
        km += step_km

    return milestones
