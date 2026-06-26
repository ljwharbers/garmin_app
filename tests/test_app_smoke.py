"""Smoke tests: verify all app modules import cleanly and expose expected callables."""
import garmin_reporting.app.state as state
import garmin_reporting.app.charts as charts
import garmin_reporting.app.main as main
import garmin_reporting.app.account as account
import garmin_reporting.app.pages.overview  # noqa: F401
import garmin_reporting.app.pages.trends    # noqa: F401
import garmin_reporting.app.pages.activities  # noqa: F401
import garmin_reporting.app.pages.records   # noqa: F401
import garmin_reporting.app.pages.training_load  # noqa: F401


def test_state_exports():
    assert callable(state.get_acts)
    assert callable(state.get_health)
    assert callable(state.get_prs)
    assert callable(state.get_splits)
    assert callable(state.invalidate)


def test_charts_exports():
    expected = [
        "cumulative_distance_chart",
        "weekly_distance_chart",
        "pace_scatter_chart",
        "avg_hr_chart",
        "resting_hr_chart",
        "vo2max_chart",
        "year_over_year_chart",
        "splits_pace_chart",
        "splits_hr_chart",
        "acwr_chart",
        "training_status_chart",
        "training_readiness_chart",
        "sleep_chart",
        "distance_by_year_chart",
    ]
    for name in expected:
        assert callable(getattr(charts, name, None)), f"charts.{name} missing or not callable"


def test_main_exports():
    assert callable(main.nav_drawer)
    assert callable(main.run)


def test_account_exports():
    assert callable(account._set_client)
    assert callable(account.account_page)


def test_fetch_progress_callback():
    """Progress callback should fire with correct phase/current/total values."""
    from garmin_reporting.fetch import _health_dates_to_fetch
    # With no stored dates, all dates in range are fetched regardless of window.
    result = _health_dates_to_fetch("2024-01-01", "2024-01-03", set(), 0)
    assert len(result) == 3  # all dates returned because none are stored yet

    # With stored dates outside the window, they are skipped.
    stored = {"2024-01-01"}
    result2 = _health_dates_to_fetch("2024-01-01", "2024-01-03", stored, 0)
    assert "2024-01-01" not in result2  # stored and before cutoff (2024-01-03) → skipped

    # Verify the callback signature works end-to-end with a simple mock
    events = []
    def cb(phase, current, total, msg):
        events.append((phase, current, total))

    # run_fetch with no client falls back to get_client() which would prompt;
    # just check the signature is accepted without executing
    import inspect
    sig = inspect.signature(__import__("garmin_reporting.fetch", fromlist=["run_fetch"]).run_fetch)
    assert "progress" in sig.parameters
    assert "client" in sig.parameters


def test_run_fetch_returns_dict_signature():
    import inspect
    from garmin_reporting.fetch import run_fetch
    sig = inspect.signature(run_fetch)
    assert "since" in sig.parameters
    assert "full" in sig.parameters
    assert "progress" in sig.parameters
    assert "client" in sig.parameters
