"""CLI entry point: garmin-dashboard-fetch

Refreshes the local Garmin data cache.

Usage:
    garmin-dashboard-fetch                    # incremental: since last stored activity
    garmin-dashboard-fetch --since 2025-01-01 # from a specific date
    garmin-dashboard-fetch --full             # full backfill from DEFAULT_BACKFILL_DATE
    garmin-dashboard-fetch --log-level DEBUG  # verbose output
"""
from __future__ import annotations

import argparse
import logging


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="garmin-dashboard-fetch",
        description="Refresh the local Garmin data cache.",
    )
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        help="Fetch activities and health data from this date onwards.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full backfill from the configured DEFAULT_BACKFILL_DATE.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    from garmin_reporting.fetch import run_fetch

    summary = run_fetch(since=args.since, full=args.full)
    print(
        f"Done: {summary['activities']} activities, "
        f"{summary['health_days']} health days, "
        f"{summary['prs']} personal records."
    )


if __name__ == "__main__":
    main()
