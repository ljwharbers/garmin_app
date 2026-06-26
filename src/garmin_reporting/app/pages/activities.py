from nicegui import ui
import pandas as pd
from garmin_reporting.app import state, charts
from garmin_reporting.transform import fmt_pace, fmt_duration


@ui.page("/activities")
def activities_page():
    from garmin_reporting.app.main import nav_drawer
    nav_drawer()

    with ui.column().classes("w-full p-4 gap-4"):
        ui.label("Activities").classes("text-h4")
        acts = state.get_acts()
        if acts.empty:
            ui.label("No data yet.")
            return

        all_types = sorted(acts["activity_type"].dropna().unique().tolist())
        default_types = ["running"] if "running" in all_types else all_types[:1]
        max_dist = float(acts["distance_km"].max()) if "distance_km" in acts.columns else 50.0
        selected = {"types": default_types, "start": acts["date"].min(), "end": acts["date"].max(), "min_km": 0.0, "activity_id": None}

        # Filters card
        with ui.card().classes("w-full"):
            ui.label("Filters").classes("text-h6")
            with ui.row().classes("gap-4 flex-wrap"):
                ui.select(all_types, multiple=True, label="Activity type", value=default_types, on_change=lambda e: (selected.update({"types": e.value}), table_section.refresh()))
                ui.date(value=str(acts["date"].min()), on_change=lambda e: (selected.update({"start": pd.Timestamp(e.value).date()}), table_section.refresh())).props("label=Start date")
                ui.date(value=str(acts["date"].max()), on_change=lambda e: (selected.update({"end": pd.Timestamp(e.value).date()}), table_section.refresh())).props("label=End date")
            ui.label("Min distance (km)")
            ui.slider(min=0, max=max_dist, step=0.5, value=0, on_change=lambda e: (selected.update({"min_km": e.value}), table_section.refresh()))

        @ui.refreshable
        def table_section():
            filtered = acts[
                (acts["activity_type"].isin(selected["types"])) &
                (acts["date"] >= selected["start"]) &
                (acts["date"] <= selected["end"]) &
                (acts["distance_km"] >= selected["min_km"])
            ].copy().sort_values("start_time", ascending=False)

            ui.label(f"{len(filtered)} activities").classes("text-caption")

            # Build aggrid columns and rows
            candidate_cols = {
                "date": "Date", "activity_type": "Type", "distance_km": "Distance (km)",
                "duration_fmt": "Duration", "pace_fmt": "Avg Pace", "avg_hr": "Avg HR",
                "max_hr": "Max HR", "avg_cadence": "Cadence", "elevation_gain_m": "Elevation (m)",
                "calories": "Calories", "avg_power": "Avg Power (W)", "vo2max": "VO2max"
            }
            display_cols = [k for k in candidate_cols if k in filtered.columns]
            disp = filtered[display_cols].copy()
            disp = disp.rename(columns=candidate_cols)
            for num_col in ["Distance (km)", "Avg HR", "Max HR", "Cadence", "Elevation (m)", "Calories", "Avg Power (W)", "VO2max"]:
                if num_col in disp.columns:
                    disp[num_col] = disp[num_col].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
            if "Distance (km)" in disp.columns:
                disp["Distance (km)"] = filtered["distance_km"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
            disp["Date"] = disp["Date"].apply(str)
            disp["_id"] = filtered["activity_id"].values

            col_defs = [{"headerName": v, "field": v, "sortable": True, "filter": True} for v in disp.columns if v != "_id"]
            col_defs.append({"headerName": "id", "field": "_id", "hide": True})
            rows_data = disp.to_dict("records")
            grid = ui.aggrid({"columnDefs": col_defs, "rowData": rows_data, "rowSelection": "single"}).classes("w-full h-96")

            # Detail section
            detail_container = ui.column().classes("w-full")

            @ui.refreshable
            def detail_section(activity_id):
                with detail_container:
                    if not activity_id:
                        return
                    row = filtered[filtered["activity_id"] == activity_id]
                    if row.empty:
                        return
                    r = row.iloc[0]
                    with ui.card().classes("w-full"):
                        ui.label(f"Activity detail: {r.get('activity_type', '?')} on {r.get('date', '?')}").classes("text-h6")
                        with ui.row().classes("gap-4 flex-wrap"):
                            # Each metric as a small card
                            kpis = [
                                ("Distance", f"{r['distance_km']:.2f} km" if pd.notna(r.get("distance_km")) else None),
                                ("Duration", r.get("duration_fmt")),
                                ("Avg pace", (str(r["pace_fmt"]) + " /km") if pd.notna(r.get("pace_fmt")) else None),
                                ("Avg HR", f"{r['avg_hr']:.0f} bpm" if pd.notna(r.get("avg_hr")) else None),
                                ("Elevation", f"{r['elevation_gain_m']:.0f} m" if pd.notna(r.get("elevation_gain_m")) else None),
                                ("Avg Power", f"{r['avg_power']:.0f} W" if pd.notna(r.get("avg_power")) else None),
                                ("VO2max", f"{r['vo2max']:.1f}" if pd.notna(r.get("vo2max")) else None),
                            ]
                            for lbl, val in kpis:
                                if val:
                                    with ui.card().classes("p-2"):
                                        ui.label(lbl).classes("text-caption")
                                        ui.label(val).classes("text-h6")
                        splits = state.get_splits(activity_id)
                        if splits.empty:
                            ui.label("No split data for this activity.")
                        else:
                            with ui.row().classes("w-full gap-4"):
                                with ui.card().classes("flex-1"):
                                    ui.label("Pace per split").classes("text-h6")
                                    if "pace_s_per_km" in splits.columns and splits["pace_s_per_km"].notna().any():
                                        ui.plotly(charts.splits_pace_chart(splits)).classes("w-full")
                                with ui.card().classes("flex-1"):
                                    ui.label("HR per split").classes("text-h6")
                                    if "avg_hr" in splits.columns and splits["avg_hr"].notna().any():
                                        ui.plotly(charts.splits_hr_chart(splits)).classes("w-full")
                                    else:
                                        ui.label("No HR data for splits.")
                            # Splits table
                            s_disp = splits[["split_index", "distance_m", "pace_s_per_km", "avg_hr"]].copy()
                            s_disp["split_index"] = s_disp["split_index"] + 1
                            s_disp.columns = ["Split", "Distance (m)", "Pace", "Avg HR"]
                            s_disp["Pace"] = splits["pace_s_per_km"].apply(fmt_pace)
                            s_disp["Avg HR"] = s_disp["Avg HR"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
                            s_disp["Distance (m)"] = s_disp["Distance (m)"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
                            s_cols = [{"name": c, "label": c, "field": c} for c in s_disp.columns]
                            ui.table(columns=s_cols, rows=s_disp.to_dict("records")).classes("w-full")

            async def on_row_click(e):
                aid = e.args.get("data", {}).get("_id")
                if aid:
                    selected["activity_id"] = aid
                    detail_container.clear()
                    detail_section(aid)

            grid.on("rowClicked", on_row_click)
            detail_section(None)

        table_section()
