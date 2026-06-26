from nicegui import ui
import pandas as pd
from garmin_reporting.app import state, charts
from garmin_reporting.transform import weekly_summary, monthly_summary, year_over_year


@ui.page("/trends")
def trends_page():
    from garmin_reporting.app.main import nav_drawer
    nav_drawer()

    with ui.column().classes("w-full p-4 gap-4"):
        ui.label("Trends").classes("text-h4")
        acts = state.get_acts()
        health = state.get_health()
        if acts.empty:
            ui.label("No data yet.")
            return

        all_types = sorted(acts["activity_type"].dropna().unique().tolist())
        default_types = ["running"] if "running" in all_types else all_types[:1]
        selected = {"types": default_types, "start": acts["date"].min(), "end": acts["date"].max(), "period": "Weekly"}

        # Filters
        with ui.card().classes("w-full"):
            ui.label("Filters").classes("text-h6")
            with ui.row().classes("gap-4 flex-wrap"):
                ui.select(all_types, multiple=True, label="Activity type", value=default_types, on_change=lambda e: (selected.update({"types": e.value}), charts_section.refresh()))
                ui.date(value=str(acts["date"].min()), on_change=lambda e: (selected.update({"start": pd.Timestamp(e.value).date()}), charts_section.refresh())).props("label=Start date")
                ui.date(value=str(acts["date"].max()), on_change=lambda e: (selected.update({"end": pd.Timestamp(e.value).date()}), charts_section.refresh())).props("label=End date")
                ui.toggle(["Weekly", "Monthly"], value="Weekly", on_change=lambda e: (selected.update({"period": e.value}), charts_section.refresh()))

        @ui.refreshable
        def charts_section():
            filtered = acts[
                (acts["activity_type"].isin(selected["types"])) &
                (acts["date"] >= selected["start"]) &
                (acts["date"] <= selected["end"])
            ].copy()
            if not health.empty:
                filtered_health = health[
                    (health["date"].dt.date >= selected["start"]) &
                    (health["date"].dt.date <= selected["end"])
                ].copy()
            else:
                filtered_health = health

            primary_type = selected["types"][0] if selected["types"] else None

            # Weekly/Monthly distance
            with ui.card().classes("w-full"):
                ui.label(f'{"Weekly" if selected["period"] == "Weekly" else "Monthly"} distance').classes("text-h6")
                frames = []
                for t in selected["types"]:
                    fn = weekly_summary if selected["period"] == "Weekly" else monthly_summary
                    s = fn(filtered, activity_type=t)
                    if not s.empty:
                        s["type"] = t
                        frames.append(s)
                if frames:
                    concat_df = pd.concat(frames, ignore_index=True)
                    ui.plotly(charts.weekly_distance_chart(concat_df, selected["period"])).classes("w-full")

            # Pace scatter
            if not filtered.empty and "avg_pace_s_per_km" in filtered.columns and filtered["avg_pace_s_per_km"].notna().any():
                with ui.card().classes("w-full"):
                    ui.label("Pace over time").classes("text-h6")
                    ui.plotly(charts.pace_scatter_chart(filtered)).classes("w-full")

            # Avg HR trend
            if not filtered.empty and "avg_hr" in filtered.columns and filtered["avg_hr"].notna().any():
                with ui.card().classes("w-full"):
                    ui.label("Average HR trend").classes("text-h6")
                    ui.plotly(charts.avg_hr_chart(filtered)).classes("w-full")

            # Resting HR and VO2max side by side
            with ui.row().classes("w-full gap-4"):
                with ui.card().classes("flex-1"):
                    ui.label("Resting HR").classes("text-h6")
                    if not filtered_health.empty and "resting_hr" in filtered_health.columns and filtered_health["resting_hr"].notna().any():
                        ui.plotly(charts.resting_hr_chart(filtered_health)).classes("w-full")
                    else:
                        ui.label("No resting HR data available.")
                with ui.card().classes("flex-1"):
                    ui.label("VO₂max trend").classes("text-h6")
                    if not filtered_health.empty and "vo2max" in filtered_health.columns and filtered_health["vo2max"].notna().any():
                        ui.plotly(charts.vo2max_chart(filtered_health)).classes("w-full")
                    else:
                        ui.label("No VO₂max data available.")

            # Year-over-year
            if primary_type and not filtered.empty:
                with ui.card().classes("w-full"):
                    ui.label(f"Year-over-year — cumulative distance ({primary_type})").classes("text-h6")
                    yoy = year_over_year(filtered, activity_type=primary_type)
                    if not yoy.empty:
                        ui.plotly(charts.year_over_year_chart(yoy)).classes("w-full")

        charts_section()
