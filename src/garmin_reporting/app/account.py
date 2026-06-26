from nicegui import ui, run as nicegui_run
import threading
import logging
from garmin_reporting.auth import login_with_tokens, begin_login, complete_login
from garmin_reporting.fetch import run_fetch
from garmin_reporting.db import get_latest_activity_date, get_activities_df, get_daily_health_df
from garmin_reporting.app import state

_g = {"client": None, "mfa_state": None, "mfa_client": None}


def _set_client(client):
    _g["client"] = client


@ui.page("/account")
def account_page():
    from garmin_reporting.app.main import nav_drawer
    nav_drawer()

    with ui.column().classes("w-full p-4 gap-4"):
        ui.label("Data & Account").classes("text-h4")

        # --- Data status section ---
        with ui.card().classes("w-full") as status_card:
            ui.label("Data Status").classes("text-h6")
            last_act_label = ui.label("")
            n_acts_label = ui.label("")
            n_health_label = ui.label("")

            def refresh_status():
                try:
                    ld = get_latest_activity_date()
                    last_act_label.set_text(f"Last activity: {ld[:10] if ld else 'none'}")
                    n_acts_label.set_text(f"Activities: {len(get_activities_df())}")
                    n_health_label.set_text(f"Health days: {len(get_daily_health_df())}")
                except Exception as e:
                    last_act_label.set_text(f"Error reading DB: {e}")

            refresh_status()
            ui.button("Refresh status", on_click=refresh_status, icon="refresh").props("flat")

        # --- Login section ---
        with ui.card().classes("w-full") as login_card:
            ui.label("Garmin Connect Login").classes("text-h6")
            status_label = ui.label("")

            # Try token login immediately
            try:
                c = login_with_tokens()
                if c:
                    _g["client"] = c
                    status_label.set_text("Logged in via cached tokens.")
                    status_label.classes("text-green-600")
            except Exception:
                pass

            with ui.column().classes("gap-2 w-full max-w-md") as login_form:
                email_input = ui.input("Garmin email", placeholder="user@example.com")
                password_input = ui.input("Password", password=True, password_toggle_button=True)

                with ui.row().classes("gap-2 hidden") as mfa_row:
                    mfa_input = ui.input("One-time MFA code")

                    async def submit_mfa():
                        try:
                            c = await nicegui_run.io_bound(complete_login, _g["mfa_client"], _g["mfa_state"], mfa_input.value)
                            _g["client"] = c
                            status_label.set_text("MFA login complete.")
                            status_label.classes(remove="text-red-600", add="text-green-600")
                            mfa_row.classes(add="hidden")
                        except Exception as e:
                            status_label.set_text(f"MFA failed: {e}")
                            status_label.classes(add="text-red-600")

                    ui.button("Submit code", on_click=submit_mfa)

                async def do_login():
                    status_label.set_text("Logging in…")
                    status_label.classes(remove="text-green-600 text-red-600")
                    try:
                        client, mfa_state = await nicegui_run.io_bound(begin_login, email_input.value, password_input.value)
                        if mfa_state is not None:
                            _g["mfa_client"] = client
                            _g["mfa_state"] = mfa_state
                            mfa_row.classes(remove="hidden")
                            status_label.set_text("MFA required — enter the code from your authenticator app.")
                        else:
                            _g["client"] = client
                            status_label.set_text("Logged in successfully.")
                            status_label.classes(add="text-green-600")
                    except Exception as e:
                        status_label.set_text(f"Login failed: {e}")
                        status_label.classes(add="text-red-600")

                ui.button("Log in", on_click=do_login, icon="login")

        # --- Fetch section ---
        with ui.card().classes("w-full"):
            ui.label("Fetch Data").classes("text-h6")
            since_input = ui.input("Fetch from (YYYY-MM-DD, leave blank for incremental)", placeholder="2025-01-01")
            full_cb = ui.checkbox("Full backfill (from 2020-01-01)")
            fetch_btn = ui.button("Fetch now", icon="sync")
            prog_bar = ui.linear_progress(0).classes("w-full")
            prog_label = ui.label("")
            fetch_log = ui.log(max_lines=60).classes("w-full h-40")

            _fetch_state = {"current": 0, "total": 1, "phase": "", "msg": "", "done": False, "summary": None, "error": None}

            async def on_fetch():
                if _g["client"] is None:
                    ui.notify("Please log in first.", type="warning")
                    return
                fetch_btn.set_enabled(False)
                prog_bar.set_value(0)
                _fetch_state.update({"done": False, "error": None, "summary": None, "current": 0, "total": 1})

                def _progress_cb(phase, current, total, message):
                    _fetch_state.update({"phase": phase, "current": current, "total": max(total, 1), "msg": message})

                def _do_fetch():
                    try:
                        s = run_fetch(client=_g["client"], since=since_input.value.strip() or None, full=full_cb.value, progress=_progress_cb)
                        _fetch_state.update({"done": True, "summary": s, "error": None})
                    except Exception as exc:
                        _fetch_state.update({"done": True, "summary": None, "error": str(exc)})

                threading.Thread(target=_do_fetch, daemon=True).start()

                async def _poll():
                    if _fetch_state["done"]:
                        _timer.cancel()
                        fetch_btn.set_enabled(True)
                        prog_bar.set_value(1)
                        if _fetch_state["error"]:
                            ui.notify(f"Fetch failed: {_fetch_state['error']}", type="negative")
                        else:
                            s = _fetch_state["summary"]
                            ui.notify(f"Done: {s['activities']} activities, {s['health_days']} health days, {s['prs']} PRs", type="positive")
                            state.invalidate()
                            refresh_status()
                        return
                    p = _fetch_state
                    if p["total"] > 0:
                        prog_bar.set_value(p["current"] / p["total"])
                    if p["msg"]:
                        fetch_log.push(p["msg"])
                        prog_label.set_text(f"{p['phase']}: {p['current']}/{p['total']}")

                _timer = ui.timer(0.2, _poll)

            fetch_btn.on_click(on_fetch)
