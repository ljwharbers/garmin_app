import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from garmin_reporting.transform import fmt_pace

_MARGIN = dict(l=0, r=0, t=10, b=0)


def cumulative_distance_chart(df) -> go.Figure:
    if df.empty:
        return go.Figure()
    fig = px.area(
        df,
        x="date",
        y="cumulative_km",
        labels={"date": "Date", "cumulative_km": "Cumulative km"},
        template="plotly_dark",
        color_discrete_sequence=["#00CC96"],
    )
    fig.update_layout(margin=_MARGIN, height=280)
    return fig


def weekly_distance_chart(df, period="Weekly") -> go.Figure:
    if df.empty:
        return go.Figure()
    x_col = "week" if period == "Weekly" else "month"
    fig = px.bar(
        df,
        x=x_col,
        y="distance_km",
        color="type",
        barmode="stack",
        template="plotly_dark",
        height=300,
    )
    fig.update_layout(margin=_MARGIN)
    return fig


def pace_scatter_chart(df) -> go.Figure:
    if df.empty:
        return go.Figure()
    df = df.copy()
    df["pace_min"] = df["avg_pace_s_per_km"] / 60
    fig = px.scatter(
        df,
        x="start_time",
        y="pace_min",
        color="activity_type",
        trendline="lowess",
        template="plotly_dark",
        height=320,
    )
    vals = [df["pace_min"].min(), df["pace_min"].mean(), df["pace_min"].max()]
    fig.update_yaxes(
        tickvals=vals,
        ticktext=[fmt_pace(v * 60) for v in vals],
    )
    fig.update_layout(margin=_MARGIN)
    return fig


def avg_hr_chart(df) -> go.Figure:
    if df.empty:
        return go.Figure()
    rolling_hr = df["avg_hr"].rolling(8, min_periods=1).mean()
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["start_time"],
            y=df["avg_hr"],
            mode="markers",
            marker=dict(color="#EF553B", opacity=0.4),
            name="Avg HR",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["start_time"],
            y=rolling_hr,
            mode="lines",
            line=dict(color="#EF553B"),
            name="8-act MA",
        )
    )
    fig.update_layout(template="plotly_dark", height=280, margin=_MARGIN)
    return fig


def resting_hr_chart(df) -> go.Figure:
    if df.empty:
        return go.Figure()
    rolling_rhr = df["resting_hr"].rolling(14, min_periods=1).mean()
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["resting_hr"],
            mode="markers",
            marker=dict(color="#AB63FA", opacity=0.4),
            name="Resting HR",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=rolling_rhr,
            mode="lines",
            line=dict(color="#AB63FA"),
            name="14-day MA",
        )
    )
    fig.update_layout(template="plotly_dark", height=280, margin=_MARGIN)
    return fig


def vo2max_chart(df) -> go.Figure:
    if df.empty:
        return go.Figure()
    fig = px.line(
        df,
        x="date",
        y="vo2max",
        template="plotly_dark",
        color_discrete_sequence=["#00CC96"],
        height=280,
    )
    fig.update_layout(margin=_MARGIN)
    return fig


def year_over_year_chart(df) -> go.Figure:
    if df.empty:
        return go.Figure()
    yoy = df.copy()
    yoy["year"] = yoy["year"].astype(str)
    fig = px.line(
        yoy,
        x="week_of_year",
        y="cumulative_km",
        color="year",
        template="plotly_dark",
        height=320,
    )
    fig.update_layout(margin=_MARGIN)
    return fig


def splits_pace_chart(splits) -> go.Figure:
    if splits.empty:
        return go.Figure()
    splits = splits.copy()
    splits["lap"] = splits["split_index"] + 1
    splits["pace_min"] = splits["pace_s_per_km"] / 60
    splits["pace_fmt"] = splits["pace_s_per_km"].apply(fmt_pace)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=splits["lap"],
            y=splits["pace_min"],
            marker_color="#636EFA",
            text=splits["pace_fmt"],
            textposition="outside",
        )
    )
    fig.update_layout(template="plotly_dark", height=320, margin=_MARGIN)
    return fig


def splits_hr_chart(splits) -> go.Figure:
    if splits.empty:
        return go.Figure()
    if splits["avg_hr"].isna().all():
        return go.Figure()
    splits = splits.copy()
    splits["lap"] = splits["split_index"] + 1
    fig = px.line(
        splits,
        x="lap",
        y="avg_hr",
        markers=True,
        template="plotly_dark",
        color_discrete_sequence=["#EF553B"],
        height=320,
    )
    fig.update_layout(margin=_MARGIN)
    return fig


def acwr_chart(df) -> go.Figure:
    if df.empty:
        return go.Figure()
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=df["distance_km"],
            marker_color="#636EFA",
            opacity=0.5,
            name="Daily distance",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["acute_load"],
            mode="lines",
            line=dict(color="#00CC96"),
            name="Acute load",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["chronic_load"],
            mode="lines",
            line=dict(color="#FFA15A"),
            name="Chronic load",
        )
    )
    fig.update_layout(template="plotly_dark", height=340, margin=_MARGIN)
    return fig


def training_status_chart(df) -> go.Figure:
    if df.empty:
        return go.Figure()
    counts = df["training_status"].value_counts().reset_index()
    counts.columns = ["Status", "Days"]
    fig = px.bar(
        counts,
        x="Status",
        y="Days",
        color="Status",
        text_auto=True,
        template="plotly_dark",
        height=300,
    )
    fig.update_layout(showlegend=False, margin=_MARGIN)
    return fig


def training_readiness_chart(df) -> go.Figure:
    if df.empty:
        return go.Figure()
    fig = px.line(
        df,
        x="date",
        y="training_readiness",
        template="plotly_dark",
        color_discrete_sequence=["#FFA15A"],
        height=280,
    )
    fig.add_hrect(y0=67, y1=100, fillcolor="#00CC96", opacity=0.15, line_width=0)
    fig.add_hrect(y0=34, y1=67, fillcolor="#FFA15A", opacity=0.15, line_width=0)
    fig.add_hrect(y0=0, y1=34, fillcolor="#EF553B", opacity=0.15, line_width=0)
    fig.update_layout(margin=_MARGIN)
    return fig


def sleep_chart(df) -> go.Figure:
    if df.empty:
        return go.Figure()
    rolling_sleep = df["sleep_hours"].rolling(7, min_periods=1).mean()
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=df["sleep_hours"],
            marker_color="#636EFA",
            opacity=0.5,
            name="Sleep hours",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=rolling_sleep,
            mode="lines",
            line=dict(color="#AB63FA"),
            name="7-day MA",
        )
    )
    fig.add_hline(
        y=8,
        line_dash="dash",
        line_color="#00CC96",
        annotation_text="8h target",
    )
    fig.update_layout(template="plotly_dark", height=280, margin=_MARGIN)
    return fig


def distance_by_year_chart(df) -> go.Figure:
    if df.empty:
        return go.Figure()
    yearly = df.groupby("year")["distance_km"].sum().reset_index()
    fig = px.bar(
        yearly,
        x="year",
        y="distance_km",
        text_auto=".0f",
        template="plotly_dark",
        color_discrete_sequence=["#636EFA"],
        height=300,
    )
    fig.update_layout(margin=_MARGIN)
    return fig
