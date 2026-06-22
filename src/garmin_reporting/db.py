"""SQLite schema definition and read/write helpers.

All persistence goes through this module.  Uses stdlib sqlite3 — no ORM.
The database lives at data/garmin.db (gitignored).
"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pandas as pd

from config import DB_PATH


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS activities (
    activity_id       TEXT PRIMARY KEY,
    start_time        TEXT,          -- ISO-8601, UTC
    activity_type     TEXT,          -- e.g. "running", "cycling", "swimming"
    distance_m        REAL,
    duration_s        REAL,
    avg_pace_s_per_km REAL,          -- seconds per km (NULL for non-distance sports)
    avg_hr            REAL,
    max_hr            REAL,
    avg_cadence       REAL,
    elevation_gain_m  REAL,
    calories          REAL,
    avg_power         REAL,          -- watts; NULL if no power meter
    vo2max            REAL,
    raw_json          TEXT           -- full Garmin payload for future use
);

CREATE TABLE IF NOT EXISTS activity_splits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id   TEXT NOT NULL REFERENCES activities(activity_id),
    split_index   INTEGER,
    distance_m    REAL,
    duration_s    REAL,
    pace_s_per_km REAL,
    avg_hr        REAL,
    UNIQUE (activity_id, split_index)
);

CREATE TABLE IF NOT EXISTS daily_health (
    date              TEXT PRIMARY KEY,  -- YYYY-MM-DD
    resting_hr        REAL,
    vo2max            REAL,
    training_status   TEXT,
    training_readiness REAL,
    sleep_hours       REAL,
    hr_zone1_s        REAL,   -- time in each HR zone (seconds)
    hr_zone2_s        REAL,
    hr_zone3_s        REAL,
    hr_zone4_s        REAL,
    hr_zone5_s        REAL
);

CREATE TABLE IF NOT EXISTS personal_records (
    pr_id         TEXT PRIMARY KEY,     -- e.g. "run_5k_best_pace"
    activity_type TEXT,
    metric        TEXT,                 -- "distance_5k", "pace_best", "longest_run" …
    value         REAL,
    unit          TEXT,                 -- "s_per_km", "m", "s", …
    activity_id   TEXT,                 -- which activity achieved it
    date          TEXT                  -- YYYY-MM-DD
);
"""

CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_activities_start_time  ON activities(start_time);
CREATE INDEX IF NOT EXISTS idx_activities_type        ON activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_splits_activity        ON activity_splits(activity_id);
CREATE INDEX IF NOT EXISTS idx_daily_health_date      ON daily_health(date);
"""


def init_db() -> None:
    """Create tables and indexes if they don't exist yet."""
    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(CREATE_INDEXES_SQL)


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def upsert_activity(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        """
        INSERT INTO activities
            (activity_id, start_time, activity_type, distance_m, duration_s,
             avg_pace_s_per_km, avg_hr, max_hr, avg_cadence, elevation_gain_m,
             calories, avg_power, vo2max, raw_json)
        VALUES
            (:activity_id, :start_time, :activity_type, :distance_m, :duration_s,
             :avg_pace_s_per_km, :avg_hr, :max_hr, :avg_cadence, :elevation_gain_m,
             :calories, :avg_power, :vo2max, :raw_json)
        ON CONFLICT(activity_id) DO UPDATE SET
            start_time        = excluded.start_time,
            activity_type     = excluded.activity_type,
            distance_m        = excluded.distance_m,
            duration_s        = excluded.duration_s,
            avg_pace_s_per_km = excluded.avg_pace_s_per_km,
            avg_hr            = excluded.avg_hr,
            max_hr            = excluded.max_hr,
            avg_cadence       = excluded.avg_cadence,
            elevation_gain_m  = excluded.elevation_gain_m,
            calories          = excluded.calories,
            avg_power         = excluded.avg_power,
            vo2max            = excluded.vo2max,
            raw_json          = excluded.raw_json
        """,
        row,
    )


def upsert_splits(conn: sqlite3.Connection, activity_id: str, splits: list[dict]) -> None:
    conn.executemany(
        """
        INSERT INTO activity_splits
            (activity_id, split_index, distance_m, duration_s, pace_s_per_km, avg_hr)
        VALUES
            (:activity_id, :split_index, :distance_m, :duration_s, :pace_s_per_km, :avg_hr)
        ON CONFLICT(activity_id, split_index) DO UPDATE SET
            distance_m    = excluded.distance_m,
            duration_s    = excluded.duration_s,
            pace_s_per_km = excluded.pace_s_per_km,
            avg_hr        = excluded.avg_hr
        """,
        [{**s, "activity_id": activity_id} for s in splits],
    )


def upsert_daily_health(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        """
        INSERT INTO daily_health
            (date, resting_hr, vo2max, training_status, training_readiness,
             sleep_hours, hr_zone1_s, hr_zone2_s, hr_zone3_s, hr_zone4_s, hr_zone5_s)
        VALUES
            (:date, :resting_hr, :vo2max, :training_status, :training_readiness,
             :sleep_hours, :hr_zone1_s, :hr_zone2_s, :hr_zone3_s, :hr_zone4_s, :hr_zone5_s)
        ON CONFLICT(date) DO UPDATE SET
            resting_hr          = excluded.resting_hr,
            vo2max              = excluded.vo2max,
            training_status     = excluded.training_status,
            training_readiness  = excluded.training_readiness,
            sleep_hours         = excluded.sleep_hours,
            hr_zone1_s          = excluded.hr_zone1_s,
            hr_zone2_s          = excluded.hr_zone2_s,
            hr_zone3_s          = excluded.hr_zone3_s,
            hr_zone4_s          = excluded.hr_zone4_s,
            hr_zone5_s          = excluded.hr_zone5_s
        """,
        row,
    )


def upsert_pr(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        """
        INSERT INTO personal_records (pr_id, activity_type, metric, value, unit, activity_id, date)
        VALUES (:pr_id, :activity_type, :metric, :value, :unit, :activity_id, :date)
        ON CONFLICT(pr_id) DO UPDATE SET
            value       = excluded.value,
            unit        = excluded.unit,
            activity_id = excluded.activity_id,
            date        = excluded.date
        """,
        row,
    )


# ---------------------------------------------------------------------------
# Read helpers (return DataFrames for use in Streamlit / transforms)
# ---------------------------------------------------------------------------

def get_activities_df() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM activities ORDER BY start_time DESC",
            conn,
        )
    if not df.empty:
        df["start_time"] = pd.to_datetime(df["start_time"], utc=True).dt.tz_convert("Europe/Brussels")
    return df


def get_splits_df(activity_id: str) -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM activity_splits WHERE activity_id = ? ORDER BY split_index",
            conn,
            params=(activity_id,),
        )
    return df


def get_daily_health_df() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM daily_health ORDER BY date",
            conn,
        )
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def get_personal_records_df() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM personal_records", conn)
    return df


def get_latest_activity_date() -> str | None:
    """Return the start_time of the most recently stored activity, or None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(start_time) as latest FROM activities"
        ).fetchone()
    return row["latest"] if row and row["latest"] else None
