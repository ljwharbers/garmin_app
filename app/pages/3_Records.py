"""Records & Milestones page — PRs, streaks, cumulative distance milestones."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from garmin_reporting.db import get_activities_df, get_personal_records_df
from garmin_reporting.transform import enrich_activities
from garmin_reporting.records import (
    format_personal_records,
    longest_activity,
    fastest_pace,
    current_streak,
    longest_streak,
    distance_milestones,
)

st.set_page_config(page_title="Records · Garmin", page_icon="🏆", layout="wide")
st.title("🏆 Records & Milestones")

@st.cache_data(ttl=600)
def load():
    acts = get_activities_df()
    prs = get_personal_records_df()
    if not acts.empty:
        acts = enrich_activities(acts)
    return acts, prs

acts, prs = load()
if acts.empty:
    st.info("No data yet. Run `python -m scripts.refresh` first.")
    st.stop()

# Sidebar — activity type (mainly for running PRs)
all_types = sorted(acts["activity_type"].dropna().unique())
pr_type = st.sidebar.selectbox(
    "Activity type for PRs",
    all_types,
    index=all_types.index("running") if "running" in all_types else 0,
)

# ---------------------------------------------------------------------------
# Personal records (real Garmin PRs)
# ---------------------------------------------------------------------------
st.subheader("Personal records")
pr_display = format_personal_records(prs)
if not pr_display.empty:
    cols = st.columns(len(pr_display))
    for col, (_, row) in zip(cols, pr_display.iterrows()):
        col.metric(row["label"], row["value_fmt"],
                   help=f"Date: {row['date'] or '—'}")
else:
    st.info("No personal records found. Run `python -m scripts.refresh` to fetch them.")

st.markdown("---")

# ---------------------------------------------------------------------------
# Streak & extremes
# ---------------------------------------------------------------------------
st.subheader("Streaks & extremes")
sc1, sc2, sc3, sc4 = st.columns(4)

with sc1:
    cs = current_streak(acts)
    st.metric("Current streak", f"{cs} day{'s' if cs != 1 else ''}")
with sc2:
    ls = longest_streak(acts)
    st.metric("Longest streak (all time)", f"{ls} day{'s' if ls != 1 else ''}")
with sc3:
    la = longest_activity(acts, activity_type=pr_type)
    st.metric(f"Longest {pr_type}", f"{la.get('distance_km', '—')} km",
              help=f"{la.get('duration_fmt', '—')} · {la.get('date', '—')}")
with sc4:
    fp = fastest_pace(acts, activity_type=pr_type)
    st.metric(f"Fastest avg pace", fp.get("pace_fmt", "—") + " /km" if fp else "—",
              help=f"{fp.get('distance_km', '—')} km · {fp.get('date', '—')}")

st.markdown("---")

# ---------------------------------------------------------------------------
# Distance milestones
# ---------------------------------------------------------------------------
st.subheader(f"Distance milestones — {pr_type}")
step = st.slider("Milestone step (km)", 100, 2000, 500, step=100)
milestones = distance_milestones(acts, activity_type=pr_type, step_km=step)

if milestones:
    ms_df = pd.DataFrame(milestones)
    ms_df = ms_df.rename(columns={"milestone_km": "Milestone (km)", "date_reached": "Date reached"})
    st.dataframe(ms_df, use_container_width=True, hide_index=True)
else:
    st.info(f"No {step} km milestones reached yet for {pr_type}.")

# ---------------------------------------------------------------------------
# Total stats summary
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("All-time summary")
type_acts = acts[acts["activity_type"] == pr_type]

if not type_acts.empty:
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Total distance", f"{type_acts['distance_km'].sum():,.0f} km")
    col_b.metric("Total activities", f"{len(type_acts):,}")
    total_h = type_acts["duration_s"].sum() / 3600
    col_c.metric("Total time", f"{total_h:,.0f} h")
    col_d.metric("Total elevation", f"{type_acts['elevation_gain_m'].sum():,.0f} m")

    # Distance by year bar chart
    yearly = (
        type_acts.groupby("year")["distance_km"].sum().reset_index()
        .rename(columns={"year": "Year", "distance_km": "Distance (km)"})
    )
    yearly["Year"] = yearly["Year"].astype(str)
    fig = px.bar(yearly, x="Year", y="Distance (km)",
                 text_auto=".0f",
                 template="plotly_dark",
                 color_discrete_sequence=["#636EFA"])
    fig.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0))
    st.plotly_chart(fig, use_container_width=True)
