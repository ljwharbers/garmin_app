"""Garmin Dashboard — Home (Overview)

Run with:  streamlit run app/Home.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from garmin_reporting.db import get_activities_df, get_daily_health_df
from garmin_reporting.transform import (
    enrich_activities,
    cumulative_distance,
    fmt_pace,
    fmt_duration,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Garmin Dashboard",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Load data (cached for 10 min)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600)
def load_data():
    acts = get_activities_df()
    health = get_daily_health_df()
    if not acts.empty:
        acts = enrich_activities(acts)
    return acts, health


acts, health = load_data()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.title("🏃 Garmin Dashboard")
st.sidebar.markdown("---")

if acts.empty:
    st.warning(
        "No data yet.  Run `python -m scripts.refresh` to fetch your Garmin activities."
    )
    st.stop()

all_types = sorted(acts["activity_type"].dropna().unique())
default_types = ["running"] if "running" in all_types else all_types[:1]

selected_types = st.sidebar.multiselect(
    "Activity type", all_types, default=default_types
)

min_date = acts["date"].min()
max_date = acts["date"].max()
date_range = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range

# Apply filters
filtered = acts[
    (acts["activity_type"].isin(selected_types))
    & (acts["date"] >= start_date)
    & (acts["date"] <= end_date)
].copy()

# ---------------------------------------------------------------------------
# KPI helpers
# ---------------------------------------------------------------------------

def kpi_this_vs_last(label, this_val, last_val, fmt="auto", suffix=""):
    delta = this_val - last_val if (this_val is not None and last_val is not None) else None
    if fmt == "pace":
        display = fmt_pace(this_val) + f" /km" if this_val else "—"
        delta_display = None  # pace delta is confusing to show raw
    elif fmt == "duration":
        display = fmt_duration(this_val) if this_val else "—"
        delta_display = None
    else:
        display = f"{this_val:.1f}{suffix}" if this_val else "—"
        delta_display = f"{delta:+.1f}{suffix}" if delta is not None else None
    st.metric(label, display, delta=delta_display)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🏃 Garmin Dashboard")
st.caption("Personal activity & training overview")
st.markdown("---")

# ---------------------------------------------------------------------------
# KPI cards — this week vs last week
# ---------------------------------------------------------------------------
today = pd.Timestamp.today().date()
week_start = today - pd.Timedelta(days=today.weekday())
last_week_start = week_start - pd.Timedelta(weeks=1)

this_week = filtered[filtered["date"] >= week_start]
last_week = filtered[
    (filtered["date"] >= last_week_start) & (filtered["date"] < week_start)
]

st.subheader("This week")
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    kpi_this_vs_last(
        "Distance",
        this_week["distance_km"].sum() if not this_week.empty else 0,
        last_week["distance_km"].sum() if not last_week.empty else 0,
        suffix=" km",
    )
with c2:
    kpi_this_vs_last(
        "Activities",
        len(this_week),
        len(last_week),
        suffix="",
    )
with c3:
    tw_pace = this_week["avg_pace_s_per_km"].mean() if not this_week.empty else None
    lw_pace = last_week["avg_pace_s_per_km"].mean() if not last_week.empty else None
    st.metric("Avg pace", fmt_pace(tw_pace) + " /km" if tw_pace else "—")
with c4:
    tw_hr = this_week["avg_hr"].mean() if not this_week.empty else None
    lw_hr = last_week["avg_hr"].mean() if not last_week.empty else None
    delta_hr = f"{tw_hr - lw_hr:+.0f} bpm" if (tw_hr and lw_hr) else None
    st.metric("Avg HR", f"{tw_hr:.0f} bpm" if tw_hr else "—", delta=delta_hr)
with c5:
    kpi_this_vs_last(
        "Elevation",
        this_week["elevation_gain_m"].sum() if not this_week.empty else 0,
        last_week["elevation_gain_m"].sum() if not last_week.empty else 0,
        suffix=" m",
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# Cumulative distance chart (this year)
# ---------------------------------------------------------------------------
st.subheader("Distance banked — this year")
year_acts = filtered[filtered["year"] == today.year] if "year" in filtered.columns else filtered
cum = cumulative_distance(year_acts)
if not cum.empty:
    fig = px.area(
        cum,
        x="date",
        y="cumulative_km",
        labels={"cumulative_km": "Cumulative km", "date": ""},
        template="plotly_dark",
        color_discrete_sequence=["#00CC96"],
    )
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=280)
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Recent activities table
# ---------------------------------------------------------------------------
st.subheader("Recent activities")
display_cols = ["date", "activity_type", "distance_km", "duration_fmt", "pace_fmt", "avg_hr", "elevation_gain_m"]
available = [c for c in display_cols if c in filtered.columns]
recent = filtered.sort_values("start_time", ascending=False).head(20)[available]
recent = recent.rename(columns={
    "date": "Date",
    "activity_type": "Type",
    "distance_km": "Distance (km)",
    "duration_fmt": "Duration",
    "pace_fmt": "Avg Pace",
    "avg_hr": "Avg HR",
    "elevation_gain_m": "Elevation (m)",
})
if "Distance (km)" in recent.columns:
    recent["Distance (km)"] = recent["Distance (km)"].round(2)
if "Avg HR" in recent.columns:
    recent["Avg HR"] = recent["Avg HR"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
st.dataframe(recent, use_container_width=True, hide_index=True)
