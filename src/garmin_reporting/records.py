"""Compute personal records, streaks, and milestones from local activity data.

These are derived from the activities DataFrame — no API calls required.
"""
from __future__ import annotations

import pandas as pd

from garmin_reporting.transform import enrich_activities, fmt_duration

_PR_TYPE_MAP = {
    1: ("Fastest 1 km",          "s"),
    2: ("Fastest Mile",          "s"),
    3: ("Fastest 5K",            "s"),
    4: ("Fastest 10K",           "s"),
    5: ("Fastest Half Marathon", "s"),
    6: ("Fastest Marathon",      "s"),
    7: ("Longest Run",           "m"),
}


def format_personal_records(prs_df: pd.DataFrame) -> pd.DataFrame:
    """Format the personal_records table rows for display.

    Skips unknown typeIds and lifetime-aggregate rows (activity_id == '0').
    Returns columns: label, value_fmt, date, activity_id.
    """
    if prs_df.empty:
        return pd.DataFrame(columns=["label", "value_fmt", "date", "activity_id"])

    rows = []
    for _, pr in prs_df.iterrows():
        pr_id = str(pr.get("pr_id", ""))
        try:
            type_id = int(pr_id.rsplit("_", 1)[-1])
        except ValueError:
            continue
        if type_id not in _PR_TYPE_MAP:
            continue
        activity_id = str(pr.get("activity_id", "0") or "0")
        if activity_id == "0":
            continue

        label, unit_type = _PR_TYPE_MAP[type_id]
        value = pr.get("value")
        if value is None or pd.isna(value):
            continue

        if unit_type == "s":
            value_fmt = fmt_duration(float(value))
        else:  # "m"
            value_fmt = f"{float(value) / 1000:.2f} km"

        rows.append({
            "label": label,
            "value_fmt": value_fmt,
            "date": str(pr.get("date") or ""),
            "activity_id": activity_id,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["label", "value_fmt", "date", "activity_id"])


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
