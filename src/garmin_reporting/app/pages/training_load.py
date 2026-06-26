from nicegui import ui
import pandas as pd
from garmin_reporting.app import state, charts
from garmin_reporting.transform import rolling_load


@ui.page("/training-load")
def training_load_page():
    from garmin_reporting.app.main import nav_drawer
    nav_drawer()

    with ui.column().classes("w-full p-4 gap-4"):
        ui.label("Training Load & Health").classes("text-h4")
        acts = state.get_acts()
        health = state.get_health()
        if acts.empty and health.empty:
            ui.label("No data yet.")
            return

        all_types = sorted(acts["activity_type"].dropna().unique().tolist()) if not acts.empty else []
        default_types = ["running"] if "running" in all_types else (all_types[:1] if all_types else [])
        act_min = acts["date"].min() if not acts.empty else pd.Timestamp.today().date()
        act_max = acts["date"].max() if not acts.empty else pd.Timestamp.today().date()
        selected = {"types": default_types, "start": act_min, "end": act_max}

        with ui.card().classes("w-full"):
            ui.label("Filters").classes("text-h6")
            with ui.row().classes("gap-4 flex-wrap"):
                ui.select(all_types, multiple=True, label="Activity types for load", value=default_types, on_change=lambda e: (selected.update({"types": e.value}), charts_section.refresh()))
                ui.date(value=str(act_min), on_change=lambda e: (selected.update({"start": pd.Timestamp(e.value).date()}), charts_section.refresh())).props("label=Start date")
                ui.date(value=str(act_max), on_change=lambda e: (selected.update({"end": pd.Timestamp(e.value).date()}), charts_section.refresh())).props("label=End date")

        @ui.refreshable
        def charts_section():
            if not acts.empty:
                filtered_acts = acts[
                    (acts["activity_type"].isin(selected["types"])) &
                    (acts["date"] >= selected["start"]) &
                    (acts["date"] <= selected["end"])
                ].copy()
            else:
                filtered_acts = acts
            if not health.empty:
                filtered_health = health[
                    (health["date"].dt.date >= selected["start"]) &
                    (health["date"].dt.date <= selected["end"])
                ].copy()
            else:
                filtered_health = health

            primary_type = selected["types"][0] if selected["types"] else None

            # ACWR chart
            with ui.card().classes("w-full"):
                ui.label("Training load — acute vs chronic (ACWR)").classes("text-h6")
                if not filtered_acts.empty:
                    load_df = rolling_load(filtered_acts, activity_type=primary_type)
                    if not load_df.empty:
                        ui.plotly(charts.acwr_chart(load_df)).classes("w-full")
                        acwr_now = load_df.iloc[-1]["acwr"] if "acwr" in load_df.columns else None
                        if acwr_now is not None and pd.notna(acwr_now):
                            if 0.8 <= acwr_now <= 1.3:
                                zone_text = "🟢 Optimal (0.8–1.3)"
                                zone_class = "text-green-600"
                            elif acwr_now > 1.5 or acwr_now < 0.5:
                                zone_text = "🔴 High risk — reduce load"
                                zone_class = "text-red-600"
                            else:
                                zone_text = "🟡 Caution"
                                zone_class = "text-amber-600"
                            with ui.row().classes("gap-4"):
                                with ui.card().classes("p-2"):
                                    ui.label("Current ACWR").classes("text-caption")
                                    ui.label(f"{acwr_now:.2f}").classes("text-h5")
                                ui.label(zone_text).classes(zone_class + " self-center")
                else:
                    ui.label("No activity data for selected filters.")

            # Training status and readiness side by side
            with ui.row().classes("w-full gap-4"):
                with ui.card().classes("flex-1"):
                    ui.label("Training status").classes("text-h6")
                    if not filtered_health.empty and "training_status" in filtered_health.columns and filtered_health["training_status"].notna().any():
                        ui.plotly(charts.training_status_chart(filtered_health)).classes("w-full")
                    else:
                        ui.label("No training status data.")
                with ui.card().classes("flex-1"):
                    ui.label("Training readiness").classes("text-h6")
                    if not filtered_health.empty and "training_readiness" in filtered_health.columns and filtered_health["training_readiness"].notna().any():
                        ui.plotly(charts.training_readiness_chart(filtered_health)).classes("w-full")
                    else:
                        ui.label("No readiness data.")

            # Sleep chart
            with ui.card().classes("w-full"):
                ui.label("Sleep").classes("text-h6")
                if not filtered_health.empty and "sleep_hours" in filtered_health.columns and filtered_health["sleep_hours"].notna().any():
                    ui.plotly(charts.sleep_chart(filtered_health)).classes("w-full")
                else:
                    ui.label("No sleep data available.")

        charts_section()
