from nicegui import ui
import pandas as pd
from datetime import timedelta
from garmin_reporting.app import state, charts
from garmin_reporting.transform import cumulative_distance, fmt_pace, fmt_duration


def _kpi_card(label, value_str, delta_str=None, delta_positive=None):
    with ui.card().classes("p-4 min-w-[150px]"):
        ui.label(label).classes("text-caption text-grey")
        ui.label(value_str).classes("text-h5 font-bold")
        if delta_str is not None:
            color = "text-green" if delta_positive else "text-red"
            ui.label(delta_str).classes(f"text-caption {color}")


@ui.page("/")
def overview_page():
    # Import nav_drawer only when called to avoid circular import
    from garmin_reporting.app.main import nav_drawer
    nav_drawer()

    with ui.column().classes("w-full p-4 gap-4"):
        ui.label("Overview").classes("text-h4")
        ui.label("Personal activity & training overview").classes("text-caption")

        # Filters in a card
        acts = state.get_acts()
        if acts.empty:
            ui.label("No data yet. Use the Data & Account page to fetch your Garmin data.")
            return

        all_types = sorted(acts["activity_type"].dropna().unique().tolist())
        default_types = ["running"] if "running" in all_types else all_types[:1]

        # Use @ui.refreshable for the content that depends on filters
        selected = {"types": default_types, "start": acts["date"].min(), "end": acts["date"].max()}

        @ui.refreshable
        def content():
            filtered = acts[
                (acts["activity_type"].isin(selected["types"])) &
                (acts["date"] >= selected["start"]) &
                (acts["date"] <= selected["end"])
            ].copy()

            today = pd.Timestamp.today().date()
            week_start = today - timedelta(days=today.weekday())
            last_week_start = week_start - timedelta(weeks=1)
            this_week = filtered[filtered["date"] >= week_start]
            last_week = filtered[(filtered["date"] >= last_week_start) & (filtered["date"] < week_start)]

            # KPI row
            with ui.card().classes("w-full"):
                ui.label("This week").classes("text-h6")
                with ui.row().classes("w-full gap-4 flex-wrap"):
                    tw_dist = this_week["distance_km"].sum() if not this_week.empty else 0
                    lw_dist = last_week["distance_km"].sum() if not last_week.empty else 0
                    _kpi_card("Distance", f"{tw_dist:.1f} km", f"{tw_dist-lw_dist:+.1f} km", tw_dist >= lw_dist)
                    tw_cnt = len(this_week); lw_cnt = len(last_week)
                    _kpi_card("Activities", str(tw_cnt), f"{tw_cnt-lw_cnt:+d}", tw_cnt >= lw_cnt)
                    tw_pace = this_week["avg_pace_s_per_km"].mean() if not this_week.empty and this_week["avg_pace_s_per_km"].notna().any() else None
                    _kpi_card("Avg pace", (fmt_pace(tw_pace) + " /km") if tw_pace else "—")
                    tw_hr = this_week["avg_hr"].mean() if not this_week.empty and this_week["avg_hr"].notna().any() else None
                    lw_hr = last_week["avg_hr"].mean() if not last_week.empty and last_week["avg_hr"].notna().any() else None
                    hr_delta = f"{tw_hr-lw_hr:+.0f} bpm" if (tw_hr and lw_hr) else None
                    _kpi_card("Avg HR", f"{tw_hr:.0f} bpm" if tw_hr else "—", hr_delta, tw_hr and lw_hr and tw_hr <= lw_hr)
                    tw_elev = this_week["elevation_gain_m"].sum() if not this_week.empty else 0
                    lw_elev = last_week["elevation_gain_m"].sum() if not last_week.empty else 0
                    _kpi_card("Elevation", f"{tw_elev:.0f} m", f"{tw_elev-lw_elev:+.0f} m", tw_elev >= lw_elev)

            # Cumulative distance chart
            with ui.card().classes("w-full"):
                ui.label("Distance banked — this year").classes("text-h6")
                year_acts = filtered[filtered["year"] == today.year] if "year" in filtered.columns else filtered
                cum = cumulative_distance(year_acts)
                if not cum.empty:
                    ui.plotly(charts.cumulative_distance_chart(cum)).classes("w-full")

            # Recent activities table
            with ui.card().classes("w-full"):
                ui.label("Recent activities").classes("text-h6")
                display_cols = ["date", "activity_type", "distance_km", "duration_fmt", "pace_fmt", "avg_hr", "elevation_gain_m"]
                available = [c for c in display_cols if c in filtered.columns]
                recent = filtered.sort_values("start_time", ascending=False).head(20)[available].copy()
                recent = recent.rename(columns={"date": "Date", "activity_type": "Type", "distance_km": "Distance (km)", "duration_fmt": "Duration", "pace_fmt": "Avg Pace", "avg_hr": "Avg HR", "elevation_gain_m": "Elevation (m)"})
                if "Distance (km)" in recent.columns:
                    recent["Distance (km)"] = recent["Distance (km)"].round(2)
                if "Avg HR" in recent.columns:
                    recent["Avg HR"] = recent["Avg HR"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
                if "Elevation (m)" in recent.columns:
                    recent["Elevation (m)"] = recent["Elevation (m)"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
                cols = [{"name": c, "label": c, "field": c} for c in recent.columns]
                rows = recent.to_dict("records")
                # Convert any non-serializable types
                for row in rows:
                    for k, v in row.items():
                        if hasattr(v, "date"):
                            row[k] = str(v)
                ui.table(columns=cols, rows=rows).classes("w-full")

        with ui.card().classes("w-full"):
            ui.label("Filters").classes("text-h6")
            with ui.row().classes("gap-4 flex-wrap"):
                type_sel = ui.select(all_types, multiple=True, label="Activity type", value=default_types, on_change=lambda e: (selected.update({"types": e.value}), content.refresh()))
                start_pick = ui.date(value=str(acts["date"].min()), on_change=lambda e: (selected.update({"start": pd.Timestamp(e.value).date()}), content.refresh())).props("label='Start date'")
                end_pick = ui.date(value=str(acts["date"].max()), on_change=lambda e: (selected.update({"end": pd.Timestamp(e.value).date()}), content.refresh())).props("label='End date'")

        content()
