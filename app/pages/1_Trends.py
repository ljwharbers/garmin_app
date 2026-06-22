"""Trends page — weekly/monthly volumes, pace & HR over time, VO2max, YoY."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from garmin_reporting.db import get_activities_df, get_daily_health_df
from garmin_reporting.transform import (
    enrich_activities,
    weekly_summary,
    monthly_summary,
    year_over_year,
    fmt_pace,
)

st.set_page_config(page_title="Trends · Garmin", page_icon="📈", layout="wide")
st.title("📈 Trends")

@st.cache_data(ttl=600)
def load():
    acts = get_activities_df()
    health = get_daily_health_df()
    if not acts.empty:
        acts = enrich_activities(acts)
    return acts, health

acts, health = load()
if acts.empty:
    st.info("No data yet. Run `python -m scripts.refresh` first.")
    st.stop()

# Sidebar
all_types = sorted(acts["activity_type"].dropna().unique())
default_types = ["running"] if "running" in all_types else all_types[:1]
sel_types = st.sidebar.multiselect("Activity type", all_types, default=default_types, key="trends_types")
min_date, max_date = acts["date"].min(), acts["date"].max()
date_range = st.sidebar.date_input("Date range", value=(min_date, max_date),
                                    min_value=min_date, max_value=max_date, key="trends_dates")
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    s_date, e_date = date_range
else:
    s_date = e_date = date_range

period = st.sidebar.radio("Aggregation", ["Weekly", "Monthly"], index=0, key="trends_period")

filtered = acts[
    acts["activity_type"].isin(sel_types)
    & (acts["date"] >= s_date)
    & (acts["date"] <= e_date)
]

# For single-type summary, use the first selected type.
primary_type = sel_types[0] if sel_types else None

# ---------------------------------------------------------------------------
# Volume bars (distance)
# ---------------------------------------------------------------------------
st.subheader(f"{'Weekly' if period == 'Weekly' else 'Monthly'} distance")
if primary_type:
    summary_fn = weekly_summary if period == "Weekly" else monthly_summary
    col_name = "week" if period == "Weekly" else "month"
    # Multi-type stacked bars
    frames = []
    for t in sel_types:
        s = summary_fn(filtered, activity_type=t)
        s["type"] = t
        frames.append(s)
    if frames:
        vol = pd.concat(frames)
        fig = px.bar(vol, x=col_name, y="distance_km", color="type",
                     barmode="stack",
                     labels={"distance_km": "Distance (km)", col_name: ""},
                     template="plotly_dark")
        fig.update_layout(legend_title_text="Type", height=300, margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Pace over time (scatter + trendline)
# ---------------------------------------------------------------------------
st.subheader("Pace over time")
pace_df = filtered.dropna(subset=["avg_pace_s_per_km"]).copy()
if not pace_df.empty:
    pace_df["pace_min"] = pace_df["avg_pace_s_per_km"] / 60  # min/km for Plotly axis
    fig2 = px.scatter(
        pace_df.sort_values("start_time"),
        x="start_time",
        y="pace_min",
        color="activity_type",
        trendline="lowess",
        labels={"pace_min": "min/km", "start_time": ""},
        template="plotly_dark",
        hover_data={"distance_km": True, "pace_fmt": True, "pace_min": False},
    )
    # Format y-axis as M:SS
    tick_vals = [i * 0.5 + pace_df["pace_min"].min() for i in range(10)]
    tick_text = [fmt_pace(v * 60) for v in tick_vals]
    fig2.update_yaxes(tickvals=tick_vals, ticktext=tick_text)
    fig2.update_layout(height=320, margin=dict(l=0,r=0,t=10,b=0))
    st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
# Average HR trend (moving average)
# ---------------------------------------------------------------------------
st.subheader("Average HR trend")
hr_df = filtered.dropna(subset=["avg_hr"]).sort_values("start_time")
if not hr_df.empty:
    hr_df["hr_ma"] = hr_df["avg_hr"].rolling(8, min_periods=1).mean()
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=hr_df["start_time"], y=hr_df["avg_hr"],
                               mode="markers", name="Avg HR",
                               marker=dict(opacity=0.4, size=5, color="#EF553B")))
    fig3.add_trace(go.Scatter(x=hr_df["start_time"], y=hr_df["hr_ma"],
                               mode="lines", name="8-activity MA",
                               line=dict(color="#EF553B", width=2)))
    fig3.update_layout(template="plotly_dark", height=280,
                        yaxis_title="bpm", xaxis_title="",
                        margin=dict(l=0,r=0,t=10,b=0), legend_title_text="")
    st.plotly_chart(fig3, use_container_width=True)

# ---------------------------------------------------------------------------
# Resting HR + VO2max (from daily health)
# ---------------------------------------------------------------------------
col_l, col_r = st.columns(2)

with col_l:
    st.subheader("Resting HR")
    if not health.empty and "resting_hr" in health.columns:
        rhr = health[health["resting_hr"].notna()].copy()
        if not rhr.empty:
            rhr["rhr_ma"] = rhr["resting_hr"].rolling(14, min_periods=1).mean()
            fig4 = go.Figure()
            fig4.add_trace(go.Scatter(x=rhr["date"], y=rhr["resting_hr"],
                                       mode="markers", name="RHR",
                                       marker=dict(opacity=0.4, size=4, color="#AB63FA")))
            fig4.add_trace(go.Scatter(x=rhr["date"], y=rhr["rhr_ma"],
                                       mode="lines", name="14-day MA",
                                       line=dict(color="#AB63FA", width=2)))
            fig4.update_layout(template="plotly_dark", height=260, yaxis_title="bpm",
                                margin=dict(l=0,r=0,t=10,b=0), legend_title_text="")
            st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("No resting HR data available.")

with col_r:
    st.subheader("VO₂max trend")
    if not health.empty and "vo2max" in health.columns:
        vo2 = health[health["vo2max"].notna()].copy()
        if not vo2.empty:
            fig5 = px.line(vo2, x="date", y="vo2max",
                           labels={"vo2max": "VO₂max (ml/kg/min)", "date": ""},
                           template="plotly_dark", color_discrete_sequence=["#00CC96"])
            fig5.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig5, use_container_width=True)
    else:
        st.info("No VO₂max data available.")

# ---------------------------------------------------------------------------
# Year-over-year cumulative distance
# ---------------------------------------------------------------------------
st.subheader("Year-over-year — cumulative distance")
if primary_type:
    yoy = year_over_year(filtered, activity_type=primary_type)
    if not yoy.empty:
        yoy["year"] = yoy["year"].astype(str)
        fig6 = px.line(yoy, x="week_of_year", y="cumulative_km", color="year",
                       labels={"cumulative_km": "Cumulative km", "week_of_year": "Week of year"},
                       template="plotly_dark")
        fig6.update_layout(height=320, margin=dict(l=0,r=0,t=10,b=0), legend_title_text="Year")
        st.plotly_chart(fig6, use_container_width=True)
