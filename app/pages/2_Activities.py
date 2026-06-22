"""Activities page — browse all activities; click one for split-level detail."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from garmin_reporting.db import get_activities_df, get_splits_df
from garmin_reporting.transform import enrich_activities, fmt_pace, fmt_duration

st.set_page_config(page_title="Activities · Garmin", page_icon="📋", layout="wide")
st.title("📋 Activities")

@st.cache_data(ttl=600)
def load():
    acts = get_activities_df()
    if not acts.empty:
        acts = enrich_activities(acts)
    return acts

acts = load()
if acts.empty:
    st.info("No data yet. Run `python -m scripts.refresh` first.")
    st.stop()

# Sidebar filters
all_types = sorted(acts["activity_type"].dropna().unique())
default_types = ["running"] if "running" in all_types else all_types[:1]
sel_types = st.sidebar.multiselect("Activity type", all_types, default=default_types)
min_date, max_date = acts["date"].min(), acts["date"].max()
date_range = st.sidebar.date_input("Date range", value=(min_date, max_date),
                                    min_value=min_date, max_value=max_date)
min_km = st.sidebar.slider("Min distance (km)", 0.0, float(acts["distance_km"].max()), 0.0, step=0.5)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    s_date, e_date = date_range
else:
    s_date = e_date = date_range

filtered = acts[
    acts["activity_type"].isin(sel_types)
    & (acts["date"] >= s_date)
    & (acts["date"] <= e_date)
    & (acts["distance_km"] >= min_km)
].sort_values("start_time", ascending=False)

# ---------------------------------------------------------------------------
# Activity table
# ---------------------------------------------------------------------------
display_cols = {
    "date": "Date",
    "activity_type": "Type",
    "distance_km": "km",
    "duration_fmt": "Duration",
    "pace_fmt": "Pace",
    "avg_hr": "Avg HR",
    "max_hr": "Max HR",
    "avg_cadence": "Cadence",
    "elevation_gain_m": "Elev (m)",
    "calories": "Cal",
}
table = filtered[[c for c in display_cols if c in filtered.columns]].copy()
if "distance_km" in table.columns:
    table["distance_km"] = table["distance_km"].round(2)
if "avg_hr" in table.columns:
    table["avg_hr"] = table["avg_hr"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
if "max_hr" in table.columns:
    table["max_hr"] = table["max_hr"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
if "avg_cadence" in table.columns:
    table["avg_cadence"] = table["avg_cadence"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
if "elevation_gain_m" in table.columns:
    table["elevation_gain_m"] = table["elevation_gain_m"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
if "calories" in table.columns:
    table["calories"] = table["calories"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")

table = table.rename(columns=display_cols)
st.caption(f"{len(filtered)} activities shown")
st.dataframe(table, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Per-activity detail
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Activity detail")

activity_options = (
    filtered["date"].astype(str)
    + " · "
    + filtered["activity_type"]
    + " · "
    + filtered["distance_km"].round(2).astype(str)
    + " km"
).tolist()
activity_ids = filtered["activity_id"].tolist()

if not activity_options:
    st.info("No activities match the current filters.")
    st.stop()

selected_idx = st.selectbox("Select activity", range(len(activity_options)),
                              format_func=lambda i: activity_options[i])

sel_act = filtered.iloc[selected_idx]
sel_id = activity_ids[selected_idx]

# Summary row
mc1, mc2, mc3, mc4, mc5 = st.columns(5)
mc1.metric("Distance", f"{sel_act['distance_km']:.2f} km")
mc2.metric("Duration", sel_act.get("duration_fmt", "—"))
mc3.metric("Avg pace", sel_act.get("pace_fmt", "—") + " /km")
mc4.metric("Avg HR", f"{sel_act['avg_hr']:.0f} bpm" if pd.notna(sel_act.get("avg_hr")) else "—")
mc5.metric("Elevation", f"{sel_act['elevation_gain_m']:.0f} m"
           if pd.notna(sel_act.get("elevation_gain_m")) else "—")

# Splits
@st.cache_data(ttl=600)
def load_splits(act_id):
    return get_splits_df(act_id)

splits = load_splits(sel_id)

if splits.empty:
    st.info("No split data available for this activity.")
else:
    splits["lap"] = (splits["split_index"] + 1).astype(str)
    splits["pace_fmt"] = splits["pace_s_per_km"].apply(fmt_pace)
    splits["pace_min"] = splits["pace_s_per_km"] / 60

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("**Pace per split**")
        fig_pace = go.Figure()
        fig_pace.add_trace(go.Bar(
            x=splits["lap"], y=splits["pace_min"],
            marker_color="#636EFA",
            text=splits["pace_fmt"],
            textposition="outside",
            name="Pace",
        ))
        tick_vals = [splits["pace_min"].min(), splits["pace_min"].mean(), splits["pace_min"].max()]
        tick_text = [fmt_pace(v * 60) for v in tick_vals]
        fig_pace.update_yaxes(tickvals=tick_vals, ticktext=tick_text)
        fig_pace.update_layout(
            template="plotly_dark", height=320, yaxis_title="pace",
            xaxis_title="Split", margin=dict(l=0,r=0,t=10,b=0),
        )
        st.plotly_chart(fig_pace, use_container_width=True)

    with col_r:
        st.markdown("**HR per split**")
        if splits["avg_hr"].notna().any():
            fig_hr = px.line(splits, x="lap", y="avg_hr",
                             markers=True,
                             labels={"avg_hr": "Avg HR (bpm)", "lap": "Split"},
                             template="plotly_dark",
                             color_discrete_sequence=["#EF553B"])
            fig_hr.update_layout(height=320, margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig_hr, use_container_width=True)
        else:
            st.info("No HR data for this activity's splits.")

    # Splits table
    splits_display = splits[["lap", "distance_m", "pace_fmt", "avg_hr"]].copy()
    splits_display["distance_m"] = splits_display["distance_m"].apply(
        lambda x: f"{x:.0f} m" if pd.notna(x) else "—"
    )
    splits_display["avg_hr"] = splits_display["avg_hr"].apply(
        lambda x: f"{x:.0f}" if pd.notna(x) else "—"
    )
    splits_display = splits_display.rename(columns={
        "lap": "Split", "distance_m": "Distance", "pace_fmt": "Pace", "avg_hr": "Avg HR"
    })
    st.dataframe(splits_display, use_container_width=True, hide_index=True)
