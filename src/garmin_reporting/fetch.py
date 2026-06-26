"""Fetch data from Garmin Connect and persist to the local SQLite cache.

All Garmin API calls are isolated here. The rest of the codebase only
reads from the database.

Usage (via scripts/refresh.py):
    python -m scripts.refresh                    # fetch since last stored date
    python -m scripts.refresh --since 2024-01-01 # override start date
    python -m scripts.refresh --full             # backfill from DEFAULT_BACKFILL_DATE
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta

from config import API_SLEEP_S, ACTIVITIES_BATCH, DEFAULT_BACKFILL_DATE, HEALTH_REFETCH_DAYS
from garmin_reporting.db import (
    get_conn,
    get_latest_activity_date,
    get_stored_health_dates,
    upsert_activity,
    upsert_daily_health,
    upsert_splits,
    upsert_pr,
    init_db,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(val, *keys, default=None):
    """Safely traverse a nested dict/list, returning default on any miss."""
    cur = val
    for k in keys:
        try:
            cur = cur[k]
        except (KeyError, IndexError, TypeError):
            return default
    return cur


def _scalar(val):
    """Coerce to a SQLite-bindable scalar; dicts and lists degrade to None."""
    if isinstance(val, (dict, list)):
        return None
    return val


def _pace_s_per_km(distance_m: float | None, duration_s: float | None) -> float | None:
    """Compute seconds-per-km pace; returns None if inputs are missing/zero."""
    if not distance_m or not duration_s:
        return None
    km = distance_m / 1000
    if km <= 0:
        return None
    return duration_s / km


def _date_range(start: str, end: str):
    """Yield date strings YYYY-MM-DD from start to end inclusive."""
    d = datetime.strptime(start, "%Y-%m-%d").date()
    end_d = datetime.strptime(end, "%Y-%m-%d").date()
    while d <= end_d:
        yield d.isoformat()
        d += timedelta(days=1)


# ---------------------------------------------------------------------------
# Activity parsing
# ---------------------------------------------------------------------------

def _parse_activity(raw: dict) -> dict:
    """Extract the fields we care about from a Garmin activity summary dict."""
    act_id = str(_safe(raw, "activityId", default=""))
    dist = _safe(raw, "distance")
    dur = _safe(raw, "duration")

    # Garmin returns type as a nested object
    type_obj = _safe(raw, "activityType", default={})
    act_type = _safe(type_obj, "typeKey", default="unknown")

    return {
        "activity_id": act_id,
        "start_time": _safe(raw, "startTimeGMT") or _safe(raw, "startTimeLocal"),
        "activity_type": act_type,
        "distance_m": dist,
        "duration_s": dur,
        "avg_pace_s_per_km": _pace_s_per_km(dist, dur),
        "avg_hr": _safe(raw, "averageHR"),
        "max_hr": _safe(raw, "maxHR"),
        "avg_cadence": _safe(raw, "averageRunningCadenceInStepsPerMinute")
                       or _safe(raw, "averageBikingCadenceInRevPerMinute"),
        "elevation_gain_m": _safe(raw, "elevationGain"),
        "calories": _safe(raw, "calories"),
        "avg_power": _safe(raw, "avgPower"),
        "vo2max": _safe(raw, "vO2MaxValue"),
        "raw_json": json.dumps(raw),
    }


def _parse_splits(raw_splits: dict | None) -> list[dict]:
    """Extract per-km or per-lap split rows from the splits API response."""
    if not raw_splits:
        return []

    candidates = _safe(raw_splits, "lapDTOs") or []
    splits = []
    for i, lap in enumerate(candidates):
        dist = _safe(lap, "distance")
        dur = _safe(lap, "duration")
        splits.append({
            "split_index": i,
            "distance_m": dist,
            "duration_s": dur,
            "pace_s_per_km": _pace_s_per_km(dist, dur),
            "avg_hr": _safe(lap, "averageHR"),
        })
    return splits


# ---------------------------------------------------------------------------
# Main fetch routines
# ---------------------------------------------------------------------------

def fetch_activities(client, start_date: str, end_date: str) -> int:
    """Fetch all activities in [start_date, end_date] and store them.

    Returns the number of newly stored activities.
    """
    logger.info("Fetching activities %s → %s", start_date, end_date)
    activities = client.get_activities_by_date(
        startdate=start_date,
        enddate=end_date,
        activitytype=None,  # all types
    )
    if not activities:
        logger.info("No activities found in range.")
        return 0

    count = 0
    with get_conn() as conn:
        for raw in activities:
            row = _parse_activity(raw)
            if not row["activity_id"]:
                continue
            upsert_activity(conn, row)
            count += 1

            # Fetch per-activity splits
            try:
                time.sleep(API_SLEEP_S)
                raw_splits = client.get_activity_splits(row["activity_id"])
                splits = _parse_splits(raw_splits)
                if splits:
                    upsert_splits(conn, row["activity_id"], splits)
            except Exception as exc:
                logger.warning("Could not fetch splits for %s: %s", row["activity_id"], exc)

    logger.info("Stored %d activities.", count)
    return count


def _health_dates_to_fetch(
    start_date: str, end_date: str,
    already_stored: set[str], refetch_days: int
) -> list[str]:
    """Return dates in [start_date, end_date] that should be fetched.

    Skips stored dates outside the trailing refetch_days window.
    """
    end_dt = date.fromisoformat(end_date)
    refetch_cutoff = (end_dt - timedelta(days=refetch_days)).isoformat()
    return [
        d for d in _date_range(start_date, end_date)
        if d not in already_stored or d >= refetch_cutoff
    ]


def fetch_daily_health(client, start_date: str, end_date: str) -> int:
    """Fetch daily health metrics for each date in range and store them.

    Skips dates already stored except the trailing HEALTH_REFETCH_DAYS window
    (recent metrics like sleep/readiness finalize late).

    Returns the number of days stored.
    """
    logger.info("Fetching daily health %s → %s", start_date, end_date)

    already_stored = get_stored_health_dates()
    all_dates = list(_date_range(start_date, end_date))
    to_fetch = _health_dates_to_fetch(start_date, end_date, already_stored, HEALTH_REFETCH_DAYS)
    skipped = len(all_dates) - len(to_fetch)
    if skipped:
        logger.info("Skipping %d already-stored health days (outside %d-day window).",
                    skipped, HEALTH_REFETCH_DAYS)

    count = 0
    with get_conn() as conn:
        for d in to_fetch:
            row: dict = {"date": d}

            try:
                rhr = client.get_rhr_day(d)
                row["resting_hr"] = _safe(rhr, "allMetrics", "metricsMap",
                                          "WELLNESS_RESTING_HEART_RATE", 0, "value")
            except Exception as exc:
                logger.debug("RHR %s: %s", d, exc)
                row["resting_hr"] = None

            try:
                time.sleep(API_SLEEP_S)
                mm = client.get_max_metrics(d)
                row["vo2max"] = _safe(mm, 0, "generic", "vo2MaxPreciseValue") \
                                or _safe(mm, 0, "generic", "vo2MaxValue")
            except Exception as exc:
                logger.debug("VO2max %s: %s", d, exc)
                row["vo2max"] = None

            try:
                time.sleep(API_SLEEP_S)
                ts = client.get_training_status(d)
                latest = _safe(ts, "mostRecentTrainingStatus", "latestTrainingStatusData",
                               default={}) or {}
                entry = next(iter(latest.values()), {}) if isinstance(latest, dict) else {}
                row["training_status"] = (
                    _safe(entry, "trainingStatusFeedbackPhrase")
                    or _safe(entry, "trainingStatus")
                )
            except Exception as exc:
                logger.debug("Training status %s: %s", d, exc)
                row["training_status"] = None

            try:
                time.sleep(API_SLEEP_S)
                tr = client.get_training_readiness(d)
                row["training_readiness"] = _safe(tr, "score") \
                                            or _safe(tr, "trainingReadinessDTO", "score")
            except Exception as exc:
                logger.debug("Training readiness %s: %s", d, exc)
                row["training_readiness"] = None

            try:
                time.sleep(API_SLEEP_S)
                sleep = client.get_sleep_data(d)
                secs = _safe(sleep, "dailySleepDTO", "sleepTimeSeconds")
                row["sleep_hours"] = round(secs / 3600, 2) if secs else None
            except Exception as exc:
                logger.debug("Sleep %s: %s", d, exc)
                row["sleep_hours"] = None

            row = {k: _scalar(v) for k, v in row.items()}
            upsert_daily_health(conn, row)
            count += 1
            time.sleep(API_SLEEP_S)

    logger.info("Stored health data for %d days.", count)
    return count


def fetch_personal_records(client) -> int:
    """Fetch Garmin-stored PRs and persist them. Returns record count."""
    try:
        prs = client.get_personal_record()
    except Exception as exc:
        logger.warning("Could not fetch personal records: %s", exc)
        return 0

    if not prs:
        return 0

    with get_conn() as conn:
        for pr in prs:
            activity_id = str(_safe(pr, "activityId", default=""))
            pr_id = f"{activity_id}_{_safe(pr, 'typeId', default='unknown')}"
            row = {
                "pr_id": pr_id,
                "activity_type": _safe(pr, "activityType"),
                "metric": _safe(pr, "typeKey") or _safe(pr, "prTypeLabelKey"),
                "value": _safe(pr, "value"),
                "unit": _safe(pr, "unitKey"),
                "activity_id": activity_id or None,
                "date": _safe(pr, "prStartTimeGMT", default="")[:10] or None,
            }
            upsert_pr(conn, row)

    return len(prs)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_fetch(since: str | None = None, full: bool = False) -> None:
    """Main entry point called by scripts/refresh.py."""
    from garmin_reporting.auth import get_client

    init_db()
    client = get_client()

    today = date.today().isoformat()

    if full or since:
        start_date = since if since else DEFAULT_BACKFILL_DATE
    else:
        latest = get_latest_activity_date()
        if latest:
            # Start from the day of the last stored activity (may overlap by one
            # day but upserts are idempotent).
            start_date = latest[:10]
        else:
            start_date = DEFAULT_BACKFILL_DATE

    logger.info("=== Starting fetch: %s → %s ===", start_date, today)
    n_acts = fetch_activities(client, start_date, today)
    n_health = fetch_daily_health(client, start_date, today)
    n_prs = fetch_personal_records(client)

    logger.info(
        "=== Done: %d activities, %d health days, %d PRs ===",
        n_acts, n_health, n_prs,
    )
