"""Garmin Dashboard — NiceGUI app entry point.

Entry point:  garmin-dashboard
Launch flags: --browser        (open in browser instead of native window)
              --port N         (default 8080)
              --host ADDR      (default 127.0.0.1; use 0.0.0.0 for LAN access)
"""
from __future__ import annotations
import argparse
from nicegui import ui, app as nicegui_app


def nav_drawer() -> None:
    """Render the left navigation drawer. Call once at the top of every page function."""
    with ui.left_drawer(fixed=False).classes("bg-grey-9 q-pa-sm"):
        ui.label("U0001f3c3 Garmin Dashboard").classes("text-h6 q-pa-sm text-white")
        ui.separator()
        with ui.column().classes("gap-1"):
            ui.button("Overview", on_click=lambda: ui.navigate.to("/"), icon="home").props("flat align=left color=white").classes("w-full")
            ui.button("Trends", on_click=lambda: ui.navigate.to("/trends"), icon="trending_up").props("flat align=left color=white").classes("w-full")
            ui.button("Activities", on_click=lambda: ui.navigate.to("/activities"), icon="directions_run").props("flat align=left color=white").classes("w-full")
            ui.button("Records", on_click=lambda: ui.navigate.to("/records"), icon="emoji_events").props("flat align=left color=white").classes("w-full")
            ui.button("Training Load", on_click=lambda: ui.navigate.to("/training-load"), icon="fitness_center").props("flat align=left color=white").classes("w-full")
            ui.separator()
            ui.button("Data & Account", on_click=lambda: ui.navigate.to("/account"), icon="cloud_sync").props("flat align=left color=white").classes("w-full")


@nicegui_app.on_startup
async def _on_startup() -> None:
    """Attempt silent token login on app start."""
    try:
        from garmin_reporting.auth import login_with_tokens
        from garmin_reporting.app import account as _account_mod
        client = login_with_tokens()
        if client is not None:
            _account_mod._set_client(client)
    except Exception:
        pass  # non-fatal — user can log in manually from the Account page


def run() -> None:
    """Console entry point: garmin-dashboard."""
    parser = argparse.ArgumentParser(
        prog="garmin-dashboard",
        description="Open the Garmin activity dashboard.",
    )
    parser.add_argument("--browser", action="store_true", help="Open in browser instead of native window.")
    parser.add_argument("--port", type=int, default=8080, help="Server port (default 8080).")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default 127.0.0.1). Use 0.0.0.0 to expose on LAN.")
    parser.add_argument("--window-size", default="1280x860", help='Native window size as WxH (default "1280x860").')
    args = parser.parse_args()

    # Register pages by importing the page modules (their @ui.page decorators fire on import).
    from garmin_reporting.app import account  # noqa: F401
    from garmin_reporting.app.pages import overview, trends, activities, records, training_load  # noqa: F401

    native = not args.browser
    try:
        w, h = (int(x) for x in args.window_size.split("x"))
    except Exception:
        w, h = 1280, 860

    ui.run(
        native=native,
        host=args.host,
        port=args.port,
        reload=False,
        window_size=(w, h),
        title="Garmin Dashboard",
        dark=True,
        show=not native,
    )
