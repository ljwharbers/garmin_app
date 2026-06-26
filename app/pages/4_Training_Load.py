"""Training Load & Health page — ACWR, HR zones, training status, sleep, resting HR."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from garmin_reporting.db import get_activities_df, get_daily_health_df
from garmin_reporting.transform import enrich_activities, rolling_load

st.set_page_config(page_title="Training Load · Garmin", page_icon="💪", layout="wide")
st.title("💪 Training Load & Health")

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
sel_types = st.sidebar.multiselect("Activity types for load", all_types, default=default_types)
min_date, max_date = acts["date"].min(), acts["date"].max()
date_range = st.sidebar.date_input("Date range", value=(min_date, max_date),
                                    min_value=min_date, max_value=max_date)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    s_date, e_date = date_range
else:
    s_date = e_date = date_range

filtered_acts = acts[
    acts["activity_type"].isin(sel_types)
    & (acts["date"] >= s_date)
    & (acts["date"] <= e_date)
]
filtered_health = health[
    (health["date"].dt.date >= s_date) & (health["date"].dt.date <= e_date)
] if not health.empty else health

# ---------------------------------------------------------------------------
# Rolling load (ACWR)
# ---------------------------------------------------------------------------
st.subheader("Training load — acute vs chronic (ACWR)")
primary_type = sel_types[0] if sel_types else None
load_df = rolling_load(filtered_acts, activity_type=primary_type)

if not load_df.empty:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=load_df["date"], y=load_df["distance_km"],
                         name="Daily distance (km)", marker_color="#636EFA", opacity=0.5))
    fig.add_trace(go.Scatter(x=load_df["date"], y=load_df["acute_load"],
                              mode="lines", name="Acute load (7-day sum)",
                              line=dict(color="#00CC96", width=2)))
    fig.add_trace(go.Scatter(x=load_df["date"], y=load_df["chronic_load"],
                              mode="lines", name="Chronic load (28-day avg/wk)",
                              line=dict(color="#FFA15A", width=2)))
    fig.update_layout(template="plotly_dark", height=340,
                       yaxis_title="km", xaxis_title="",
                       margin=dict(l=0,r=0,t=10,b=0), legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

    # ACWR gauge band
    acwr_now = load_df["acwr"].dropna().iloc[-1] if load_df["acwr"].notna().any() else None
    if acwr_now is not None:
        col_a, col_b = st.columns([1, 4])
        color = "#00CC96" if 0.8 <= acwr_now <= 1.3 else "#EF553B"
        col_a.metric("Current ACWR", f"{acwr_now:.2f}",
                     help="0.8–1.3 = optimal training zone. >1.3 = injury risk zone.")
        col_b.caption(
            "🟢 Optimal zone (0.8–1.3)" if 0.8 <= acwr_now <= 1.3
            else ("🔴 High injury-risk zone (>1.3)" if acwr_now > 1.3 else "🟡 Under-training zone (<0.8)")
        )

st.markdown("---")

# ---------------------------------------------------------------------------
# Training status + readiness
# ---------------------------------------------------------------------------
st.subheader("Training status & readiness")
if not filtered_health.empty:
    col_l, col_r = st.columns(2)

    with col_l:
        ts = filtered_health[filtered_health["training_status"].notna()][["date", "training_status"]]
        if not ts.empty:
            status_counts = ts["training_status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Days"]
            fig_ts = px.bar(status_counts, x="Status", y="Days", template="plotly_dark",
                            color="Status", text_auto=True)
            fig_ts.update_layout(height=280, margin=dict(l=0,r=0,t=10,b=0), showlegend=False)
            st.plotly_chart(fig_ts, use_container_width=True)
        else:
            st.info("No training status data.")

    with col_r:
        tr = filtered_health[filtered_health["training_readiness"].notna()][["date", "training_readiness"]]
        if not tr.empty:
            fig_tr = px.line(tr, x="date", y="training_readiness",
                             labels={"training_readiness": "Readiness score (0–100)", "date": ""},
                             template="plotly_dark", color_discrete_sequence=["#FFA15A"])
            fig_tr.add_hrect(y0=67, y1=100, fillcolor="green", opacity=0.1, line_width=0)
            fig_tr.add_hrect(y0=34, y1=67, fillcolor="yellow", opacity=0.08, line_width=0)
            fig_tr.add_hrect(y0=0, y1=34, fillcolor="red", opacity=0.08, line_width=0)
            fig_tr.update_layout(height=280, margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig_tr, use_container_width=True)
        else:
            st.info("No training readiness data.")

st.markdown("---")

# ---------------------------------------------------------------------------
# Sleep
# ---------------------------------------------------------------------------
st.subheader("Sleep")
if not filtered_health.empty and "sleep_hours" in filtered_health.columns:
    sleep = filtered_health[filtered_health["sleep_hours"].notna()][["date", "sleep_hours"]]
    if not sleep.empty:
        sleep["sleep_ma"] = sleep["sleep_hours"].rolling(7, min_periods=1).mean()
        fig_sl = go.Figure()
        fig_sl.add_trace(go.Bar(x=sleep["date"], y=sleep["sleep_hours"],
                                 name="Sleep (h)", marker_color="#636EFA", opacity=0.5))
        fig_sl.add_trace(go.Scatter(x=sleep["date"], y=sleep["sleep_ma"],
                                     mode="lines", name="7-day avg",
                                     line=dict(color="#AB63FA", width=2)))
        fig_sl.add_hline(y=8, line_dash="dash", line_color="green", opacity=0.5,
                          annotation_text="8h target")
        fig_sl.update_layout(template="plotly_dark", height=280,
                               yaxis_title="Hours", xaxis_title="",
                               margin=dict(l=0,r=0,t=10,b=0), legend_title_text="")
        st.plotly_chart(fig_sl, use_container_width=True)
    else:
        st.info("No sleep data available for the selected period.")
