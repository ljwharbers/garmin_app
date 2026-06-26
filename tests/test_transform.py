"""Tests for garmin_reporting.transform pure functions."""
import pandas as pd
import pytest
from garmin_reporting.transform import (
    fmt_pace, fmt_duration, enrich_activities,
    weekly_summary, monthly_summary, rolling_load,
    cumulative_distance, year_over_year,
)


# ---- fmt_pace ---------------------------------------------------------------

def test_fmt_pace_none():
    assert fmt_pace(None) == ""

def test_fmt_pace_zero():
    assert fmt_pace(0) == ""

def test_fmt_pace_round():
    assert fmt_pace(300) == "5:00"

def test_fmt_pace_seconds():
    assert fmt_pace(195) == "3:15"

def test_fmt_pace_over_ten():
    assert fmt_pace(660) == "11:00"


# ---- fmt_duration -----------------------------------------------------------

def test_fmt_duration_none():
    assert fmt_duration(None) == ""

def test_fmt_duration_under_hour():
    assert fmt_duration(90) == "1:30"

def test_fmt_duration_exact_hour():
    assert fmt_duration(3600) == "1:00:00"

def test_fmt_duration_over_hour():
    assert fmt_duration(3661) == "1:01:01"


# ---- enrich_activities fixture ----------------------------------------------

@pytest.fixture
def acts_df():
    return pd.DataFrame({
        "activity_id": ["a1", "a2"],
        "start_time": ["2024-03-10 08:00:00+00:00", "2024-03-17 09:00:00+00:00"],
        "activity_type": ["running", "running"],
        "distance_m": [10000.0, 5000.0],
        "duration_s": [3000.0, 1500.0],
        "avg_pace_s_per_km": [300.0, 300.0],
        "avg_hr": [150.0, 145.0],
        "max_hr": [170.0, 165.0],
        "avg_cadence": [180.0, 178.0],
        "elevation_gain_m": [50.0, 20.0],
        "calories": [600.0, 300.0],
        "avg_power": [None, None],
        "vo2max": [None, None],
    })


def test_enrich_adds_distance_km(acts_df):
    result = enrich_activities(acts_df)
    assert list(result["distance_km"]) == [10.0, 5.0]

def test_enrich_adds_pace_fmt(acts_df):
    result = enrich_activities(acts_df)
    assert list(result["pace_fmt"]) == ["5:00", "5:00"]

def test_enrich_adds_duration_fmt(acts_df):
    result = enrich_activities(acts_df)
    assert list(result["duration_fmt"]) == ["50:00", "25:00"]

def test_enrich_adds_date_week_month_year(acts_df):
    result = enrich_activities(acts_df)
    assert result["year"].tolist() == [2024, 2024]
    assert "week" in result.columns
    assert "month" in result.columns
    assert "date" in result.columns

def test_enrich_does_not_mutate_input(acts_df):
    original_cols = list(acts_df.columns)
    enrich_activities(acts_df)
    assert list(acts_df.columns) == original_cols


# ---- weekly_summary ---------------------------------------------------------

def test_weekly_summary_counts(acts_df):
    result = weekly_summary(acts_df)
    assert len(result) == 2  # two different weeks
    assert result["n_activities"].sum() == 2

def test_weekly_summary_type_filter(acts_df):
    result = weekly_summary(acts_df, activity_type="cycling")
    assert len(result) == 0


# ---- rolling_load -----------------------------------------------------------

def test_rolling_load_columns(acts_df):
    result = rolling_load(acts_df)
    assert "acute_load" in result.columns
    assert "chronic_load" in result.columns
    assert "acwr" in result.columns

def test_rolling_load_acute_is_7day_sum(acts_df):
    result = rolling_load(acts_df)
    # acute load on the first activity day should equal that day's distance
    first_row = result[result["distance_km"] > 0].iloc[0]
    assert first_row["acute_load"] == pytest.approx(first_row["distance_km"], rel=1e-3)


# ---- cumulative_distance ----------------------------------------------------

def test_cumulative_distance_sums(acts_df):
    result = cumulative_distance(acts_df)
    assert result["cumulative_km"].iloc[-1] == pytest.approx(15.0)

def test_cumulative_distance_type_filter(acts_df):
    result = cumulative_distance(acts_df, activity_type="cycling")
    assert result.empty


# ---- year_over_year ---------------------------------------------------------

def test_year_over_year_columns(acts_df):
    result = year_over_year(acts_df)
    assert "year" in result.columns
    assert "week_of_year" in result.columns
    assert "cumulative_km" in result.columns
