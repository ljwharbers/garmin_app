"""Tests for garmin_reporting.records pure functions."""
import pandas as pd
import pytest
from garmin_reporting.records import (
    format_personal_records,
    longest_activity, fastest_pace,
    current_streak, longest_streak,
    distance_milestones,
)


@pytest.fixture
def acts_df():
    return pd.DataFrame({
        "activity_id": ["a1", "a2", "a3"],
        "start_time": ["2024-01-01 08:00:00+00:00",
                       "2024-01-02 08:00:00+00:00",
                       "2024-01-03 08:00:00+00:00"],
        "activity_type": ["running", "running", "running"],
        "distance_m": [10000.0, 21097.0, 5000.0],
        "duration_s": [3000.0, 6360.0, 1500.0],
        "avg_pace_s_per_km": [300.0, 301.5, 300.0],
        "avg_hr": [150.0, 155.0, 145.0],
        "max_hr": [170.0, 175.0, 165.0],
        "avg_cadence": [180.0, 178.0, 182.0],
        "elevation_gain_m": [50.0, 100.0, 20.0],
        "calories": [600.0, 1200.0, 300.0],
        "avg_power": [None, None, None],
        "vo2max": [None, None, None],
    })


# ---- longest_activity -------------------------------------------------------

def test_longest_activity_returns_max(acts_df):
    result = longest_activity(acts_df, activity_type="running")
    assert result["distance_km"] == pytest.approx(21.097, rel=1e-3)

def test_longest_activity_empty_type(acts_df):
    result = longest_activity(acts_df, activity_type="cycling")
    assert result == {}


# ---- fastest_pace -----------------------------------------------------------

def test_fastest_pace_returns_min_pace(acts_df):
    result = fastest_pace(acts_df, activity_type="running", min_km=1.0)
    # a1 and a3 have pace 300 s/km; a2 has 301.5 -> fastest is a1 or a3
    assert result["pace_fmt"] == "5:00"

def test_fastest_pace_min_km_filter(acts_df):
    result = fastest_pace(acts_df, activity_type="running", min_km=15.0)
    # only a2 qualifies (21 km)
    assert result["distance_km"] == pytest.approx(21.097, rel=1e-3)


# ---- current_streak / longest_streak ----------------------------------------

@pytest.fixture
def streak_df():
    return pd.DataFrame({
        "activity_id": ["s1", "s2", "s3", "s4"],
        "start_time": [
            "2024-01-01 08:00:00+00:00",
            "2024-01-02 08:00:00+00:00",
            "2024-01-03 08:00:00+00:00",
            "2024-01-10 08:00:00+00:00",  # gap breaks streak
        ],
        "activity_type": ["running"] * 4,
        "distance_m": [5000.0] * 4,
        "duration_s": [1500.0] * 4,
        "avg_pace_s_per_km": [300.0] * 4,
        "avg_hr": [150.0] * 4,
        "max_hr": [170.0] * 4,
        "avg_cadence": [180.0] * 4,
        "elevation_gain_m": [20.0] * 4,
        "calories": [300.0] * 4,
        "avg_power": [None] * 4,
        "vo2max": [None] * 4,
    })

def test_longest_streak(streak_df):
    result = longest_streak(streak_df)
    assert result == 3

def test_current_streak_empty():
    empty = pd.DataFrame(columns=["activity_id", "start_time", "activity_type",
                                   "distance_m", "duration_s", "avg_pace_s_per_km",
                                   "avg_hr", "max_hr", "avg_cadence",
                                   "elevation_gain_m", "calories", "avg_power", "vo2max"])
    assert current_streak(empty) == 0


# ---- distance_milestones ----------------------------------------------------

def test_distance_milestones_count(acts_df):
    milestones = distance_milestones(acts_df, activity_type="running", step_km=10)
    total_km = 10.0 + 21.097 + 5.0  # 36.097
    expected_count = int(total_km // 10)  # 3
    assert len(milestones) == expected_count

def test_distance_milestones_empty_type(acts_df):
    milestones = distance_milestones(acts_df, activity_type="cycling", step_km=100)
    assert milestones == []


# ---- format_personal_records ------------------------------------------------

@pytest.fixture
def prs_df():
    return pd.DataFrame({
        "pr_id": ["111_1", "222_3", "333_7", "0_7"],
        "activity_type": ["running", "running", "running", "running"],
        "metric": [None, None, None, None],
        "value": [232.8, 1329.9, 21466.0, 50000.0],
        "unit": [None, None, None, None],
        "activity_id": ["111", "222", "333", "0"],
        "date": ["2024-01-15", "2024-02-20", "2024-03-10", None],
    })

def test_format_personal_records_skips_aggregates(prs_df):
    result = format_personal_records(prs_df)
    # The row with activity_id="0" (typeId 7, a known type) must be excluded
    assert len(result) == 3
    activity_ids = result["activity_id"].tolist()
    assert "0" not in activity_ids

def test_format_personal_records_type1_duration(prs_df):
    result = format_personal_records(prs_df)
    row = result[result["label"] == "Fastest 1 km"].iloc[0]
    assert row["value_fmt"] == "3:53"  # 232.8s → rounds to 233s = 3m53s

def test_format_personal_records_type7_km(prs_df):
    result = format_personal_records(prs_df)
    row = result[result["label"] == "Longest Run"].iloc[0]
    assert "km" in row["value_fmt"]
    assert "21.47" in row["value_fmt"]  # 21466/1000 = 21.466 -> "21.47"

def test_format_personal_records_empty():
    result = format_personal_records(pd.DataFrame())
    assert result.empty
    assert list(result.columns) == ["label", "value_fmt", "date", "activity_id"]
