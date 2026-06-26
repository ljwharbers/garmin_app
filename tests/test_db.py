"""Tests for garmin_reporting.db — round-trip and idempotency."""
import pytest
import pandas as pd
import garmin_reporting.db as db_module
from garmin_reporting.db import (
    init_db, get_conn,
    upsert_activity, upsert_splits, upsert_daily_health, upsert_pr,
    get_activities_df, get_splits_df, get_daily_health_df,
    get_personal_records_df, get_stored_health_dates, get_latest_activity_date,
)

SAMPLE_ACTIVITY = {
    "activity_id": "test_act_1",
    "start_time": "2024-03-10 08:00:00",
    "activity_type": "running",
    "distance_m": 10000.0,
    "duration_s": 3000.0,
    "avg_pace_s_per_km": 300.0,
    "avg_hr": 150.0,
    "max_hr": 170.0,
    "avg_cadence": 180.0,
    "elevation_gain_m": 50.0,
    "calories": 600.0,
    "avg_power": None,
    "vo2max": None,
    "raw_json": '{"activityId": "test_act_1"}',
}

SAMPLE_SPLITS = [
    {"split_index": 0, "distance_m": 1000.0, "duration_s": 300.0, "pace_s_per_km": 300.0, "avg_hr": 150.0},
    {"split_index": 1, "distance_m": 1000.0, "duration_s": 295.0, "pace_s_per_km": 295.0, "avg_hr": 155.0},
]

SAMPLE_HEALTH = {
    "date": "2024-03-10",
    "resting_hr": 48.0,
    "vo2max": 52.5,
    "training_status": "productive",
    "training_readiness": 75.0,
    "sleep_hours": 7.5,
}

SAMPLE_PR = {
    "pr_id": "test_act_1_3",
    "activity_type": "running",
    "metric": None,
    "value": 1329.9,
    "unit": None,
    "activity_id": "test_act_1",
    "date": "2024-03-10",
}


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """Redirect all DB operations to a fresh temp file per test."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    init_db()
    yield


# ---- activities -------------------------------------------------------------

def test_upsert_activity_round_trip():
    with get_conn() as conn:
        upsert_activity(conn, SAMPLE_ACTIVITY)
    df = get_activities_df()
    assert len(df) == 1
    assert df.iloc[0]["activity_id"] == "test_act_1"

def test_upsert_activity_idempotent():
    with get_conn() as conn:
        upsert_activity(conn, SAMPLE_ACTIVITY)
        upsert_activity(conn, SAMPLE_ACTIVITY)
    df = get_activities_df()
    assert len(df) == 1

def test_get_latest_activity_date_returns_none_when_empty():
    assert get_latest_activity_date() is None

def test_get_latest_activity_date_returns_most_recent():
    with get_conn() as conn:
        upsert_activity(conn, SAMPLE_ACTIVITY)
    result = get_latest_activity_date()
    assert result is not None
    assert "2024-03-10" in result


# ---- splits -----------------------------------------------------------------

def test_upsert_splits_round_trip():
    with get_conn() as conn:
        upsert_activity(conn, SAMPLE_ACTIVITY)
        upsert_splits(conn, "test_act_1", SAMPLE_SPLITS)
    df = get_splits_df("test_act_1")
    assert len(df) == 2

def test_upsert_splits_idempotent():
    with get_conn() as conn:
        upsert_activity(conn, SAMPLE_ACTIVITY)
        upsert_splits(conn, "test_act_1", SAMPLE_SPLITS)
        upsert_splits(conn, "test_act_1", SAMPLE_SPLITS)
    df = get_splits_df("test_act_1")
    assert len(df) == 2


# ---- daily health -----------------------------------------------------------

def test_upsert_daily_health_round_trip():
    with get_conn() as conn:
        upsert_daily_health(conn, SAMPLE_HEALTH)
    df = get_daily_health_df()
    assert len(df) == 1
    assert df.iloc[0]["resting_hr"] == 48.0

def test_upsert_daily_health_idempotent():
    with get_conn() as conn:
        upsert_daily_health(conn, SAMPLE_HEALTH)
        upsert_daily_health(conn, SAMPLE_HEALTH)
    df = get_daily_health_df()
    assert len(df) == 1

def test_get_stored_health_dates_empty():
    assert get_stored_health_dates() == set()

def test_get_stored_health_dates_returns_stored():
    with get_conn() as conn:
        upsert_daily_health(conn, SAMPLE_HEALTH)
    dates = get_stored_health_dates()
    assert "2024-03-10" in dates


# ---- personal records -------------------------------------------------------

def test_upsert_pr_round_trip():
    with get_conn() as conn:
        upsert_pr(conn, SAMPLE_PR)
    df = get_personal_records_df()
    assert len(df) == 1
    assert df.iloc[0]["pr_id"] == "test_act_1_3"

def test_upsert_pr_idempotent():
    with get_conn() as conn:
        upsert_pr(conn, SAMPLE_PR)
        upsert_pr(conn, SAMPLE_PR)
    df = get_personal_records_df()
    assert len(df) == 1
