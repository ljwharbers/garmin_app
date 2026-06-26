from nicegui import ui
import pandas as pd
from garmin_reporting.app import state
from garmin_reporting.app import charts
from garmin_reporting.records import format_personal_records, longest_activity, fastest_pace, current_streak, longest_streak, distance_milestones


@ui.page("/records")
def records_page():
    from garmin_reporting.app.main import nav_drawer
    nav_drawer()

    with ui.column().classes("w-full p-4 gap-4"):
        ui.label("Records & Milestones").classes("text-h4")
        acts = state.get_acts()
        prs = state.get_prs()
        if acts.empty:
            ui.label("No data yet.")
            return

        all_types = sorted(acts["activity_type"].dropna().unique().tolist())
        default_type = "running" if "running" in all_types else (all_types[0] if all_types else "")
        selected = {"type": default_type, "milestone_step": 500}

        with ui.card().classes("w-full"):
            with ui.row().classes("gap-4"):
                ui.select(all_types, label="Activity type", value=default_type, on_change=lambda e: (selected.update({"type": e.value}), content.refresh()))

        @ui.refreshable
        def content():
            pr_type = selected["type"]
            step = selected["milestone_step"]

            # Personal records
            with ui.card().classes("w-full"):
                ui.label("Personal records").classes("text-h6")
                if not prs.empty:
                    pr_display = format_personal_records(prs)
                    if not pr_display.empty:
                        with ui.row().classes("gap-4 flex-wrap"):
                            for _, row in pr_display.iterrows():
                                with ui.card().classes("p-2"):
                                    ui.label(row["label"]).classes("text-caption")
                                    ui.label(row["value_fmt"]).classes("text-h6")
                                    if pd.notna(row.get("date")):
                                        ui.label(str(row["date"])).classes("text-caption text-grey")
                    else:
                        ui.label("No personal records found.")
                else:
                    ui.label("No personal records data available.")

            # Streaks and extremes
            with ui.card().classes("w-full"):
                ui.label("Streaks & extremes").classes("text-h6")
                with ui.row().classes("gap-4 flex-wrap"):
                    curr = current_streak(acts)
                    with ui.card().classes("p-2"):
                        ui.label("Current streak").classes("text-caption")
                        ui.label(f"{curr} day(s)").classes("text-h6")
                    longest = longest_streak(acts)
                    with ui.card().classes("p-2"):
                        ui.label("Longest streak").classes("text-caption")
                        ui.label(f"{longest} day(s)").classes("text-h6")
                    lng = longest_activity(acts, activity_type=pr_type)
                    if lng:
                        with ui.card().classes("p-2"):
                            ui.label(f"Longest {pr_type}").classes("text-caption")
                            ui.label(f"{lng['distance_km']:.2f} km").classes("text-h6")
                            ui.label(str(lng.get("date",""))).classes("text-caption text-grey")
                    fast = fastest_pace(acts, activity_type=pr_type)
                    if fast:
                        with ui.card().classes("p-2"):
                            ui.label(f"Fastest avg pace ({pr_type})").classes("text-caption")
                            ui.label(f"{fast['pace_fmt']} /km").classes("text-h6")
                            ui.label(str(fast.get("date",""))).classes("text-caption text-grey")

            # Distance milestones
            with ui.card().classes("w-full"):
                ui.label(f"Distance milestones — {pr_type}").classes("text-h6")
                ui.label("Milestone step (km)")
                ui.slider(min=100, max=2000, step=100, value=500, on_change=lambda e: (selected.update({"milestone_step": int(e.value)}), content.refresh()))
                milestones = distance_milestones(acts, activity_type=pr_type, step_km=step)
                if milestones:
                    m_cols = [{"name": "milestone_km", "label": "Milestone (km)", "field": "milestone_km"}, {"name": "date_reached", "label": "Date reached", "field": "date_reached"}]
                    m_rows = [{"milestone_km": m["milestone_km"], "date_reached": str(m["date_reached"])} for m in milestones]
                    ui.table(columns=m_cols, rows=m_rows).classes("w-full")
                else:
                    ui.label("No milestones reached yet.")

            # All-time summary
            with ui.card().classes("w-full"):
                ui.label("All-time summary").classes("text-h6")
                with ui.row().classes("gap-4 flex-wrap"):
                    total_km = acts["distance_km"].sum() if "distance_km" in acts.columns else 0
                    with ui.card().classes("p-2"):
                        ui.label("Total distance").classes("text-caption")
                        ui.label(f"{total_km:.0f} km").classes("text-h6")
                    with ui.card().classes("p-2"):
                        ui.label("Total activities").classes("text-caption")
                        ui.label(str(len(acts))).classes("text-h6")
                    total_h = acts["duration_s"].sum() / 3600 if "duration_s" in acts.columns else 0
                    with ui.card().classes("p-2"):
                        ui.label("Total time").classes("text-caption")
                        ui.label(f"{total_h:.0f} h").classes("text-h6")
                    total_elev = acts["elevation_gain_m"].sum() if "elevation_gain_m" in acts.columns else 0
                    with ui.card().classes("p-2"):
                        ui.label("Total elevation").classes("text-caption")
                        ui.label(f"{total_elev:.0f} m").classes("text-h6")
                ui.plotly(charts.distance_by_year_chart(acts)).classes("w-full")

        content()
