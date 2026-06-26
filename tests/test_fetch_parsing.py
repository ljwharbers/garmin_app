"""Tests for pure helper functions in garmin_reporting.fetch."""
import pytest
from garmin_reporting.fetch import _pace_s_per_km, _parse_activity, _parse_splits


# ---- _pace_s_per_km ---------------------------------------------------------

def test_pace_normal():
    result = _pace_s_per_km(10000, 3000)
    assert result == pytest.approx(300.0)

def test_pace_none_distance():
    assert _pace_s_per_km(None, 3000) is None

def test_pace_none_duration():
    assert _pace_s_per_km(10000, None) is None

def test_pace_zero_distance():
    assert _pace_s_per_km(0, 3000) is None


# ---- _parse_activity --------------------------------------------------------

SAMPLE_RAW = {
    "activityId": 12345,
    "startTimeGMT": "2024-03-10 08:00:00",
    "activityType": {"typeKey": "running"},
    "distance": 10000.0,
    "duration": 3000.0,
    "averageHR": 150.0,
    "maxHR": 170.0,
    "averageRunningCadenceInStepsPerMinute": 180.0,
    "elevationGain": 50.0,
    "calories": 600.0,
    "avgPower": None,
    "vO2MaxValue": 52.5,
}

def test_parse_activity_id():
    result = _parse_activity(SAMPLE_RAW)
    assert result["activity_id"] == "12345"

def test_parse_activity_type():
    result = _parse_activity(SAMPLE_RAW)
    assert result["activity_type"] == "running"

def test_parse_activity_pace():
    result = _parse_activity(SAMPLE_RAW)
    assert result["avg_pace_s_per_km"] == pytest.approx(300.0)

def test_parse_activity_stores_raw_json():
    result = _parse_activity(SAMPLE_RAW)
    assert result["raw_json"] is not None
    import json
    parsed = json.loads(result["raw_json"])
    assert parsed["activityId"] == 12345

def test_parse_activity_missing_fields():
    result = _parse_activity({})
    assert result["activity_id"] == ""
    assert result["activity_type"] == "unknown"
    assert result["avg_pace_s_per_km"] is None


# ---- _parse_splits ----------------------------------------------------------

SAMPLE_SPLITS = {
    "lapDTOs": [
        {"distance": 1000.0, "duration": 300.0, "averageHR": 150.0},
        {"distance": 1000.0, "duration": 295.0, "averageHR": 155.0},
    ]
}

def test_parse_splits_count():
    result = _parse_splits(SAMPLE_SPLITS)
    assert len(result) == 2

def test_parse_splits_pace():
    result = _parse_splits(SAMPLE_SPLITS)
    assert result[0]["pace_s_per_km"] == pytest.approx(300.0)

def test_parse_splits_index():
    result = _parse_splits(SAMPLE_SPLITS)
    assert result[0]["split_index"] == 0
    assert result[1]["split_index"] == 1

def test_parse_splits_empty():
    assert _parse_splits(None) == []
    assert _parse_splits({}) == []

def test_parse_splits_no_lapdtos():
    assert _parse_splits({"lapDTOs": []}) == []


from garmin_reporting.fetch import _health_dates_to_fetch


# ---- _health_dates_to_fetch ------------------------------------------------

def test_health_dates_to_fetch_all_new():
    result = _health_dates_to_fetch("2024-01-01", "2024-01-05", set(), 3)
    assert result == ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]

def test_health_dates_to_fetch_skips_old_stored():
    # 01, 02, 03 stored; 04, 05 in trailing window (refetch_days=3, end=2024-01-05 → cutoff=2024-01-02)
    stored = {"2024-01-01", "2024-01-02", "2024-01-03"}
    result = _health_dates_to_fetch("2024-01-01", "2024-01-05", stored, 3)
    # cutoff = 2024-01-05 - 3 days = 2024-01-02; dates >= 2024-01-02 are re-fetched even if stored
    assert "2024-01-01" not in result  # stored and before cutoff → skipped
    assert "2024-01-02" in result       # stored but == cutoff → re-fetched
    assert "2024-01-03" in result       # stored but after cutoff → re-fetched
    assert "2024-01-04" in result       # not stored → fetched
    assert "2024-01-05" in result       # not stored → fetched

def test_health_dates_to_fetch_all_stored_outside_window():
    stored = {"2024-01-01", "2024-01-02"}
    result = _health_dates_to_fetch("2024-01-01", "2024-01-02", stored, 0)
    # refetch_days=0 → cutoff = end_date itself → only end_date is in window
    # 2024-01-01 stored and < cutoff (2024-01-02) → skip
    # 2024-01-02 stored and == cutoff → re-fetch
    assert "2024-01-01" not in result
    assert "2024-01-02" in result

def test_health_dates_to_fetch_empty_range():
    result = _health_dates_to_fetch("2024-01-05", "2024-01-04", set(), 3)
    assert result == []
