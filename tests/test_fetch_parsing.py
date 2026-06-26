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
