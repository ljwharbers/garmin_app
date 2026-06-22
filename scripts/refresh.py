#!/usr/bin/env python3
"""CLI refresh script: fetch new Garmin data into the local SQLite cache.

Usage:
    # From the project root (with venv active):
    python -m scripts.refresh                      # fetch since last stored date
    python -m scripts.refresh --since 2024-01-01   # override start date
    python -m scripts.refresh --full               # full backfill from DEFAULT_BACKFILL_DATE
"""
import argparse
import logging
import sys
from pathlib import Path

# Add project src to path so imports work without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))  # for config.py

from garmin_reporting.fetch import run_fetch


def main():
    parser = argparse.ArgumentParser(description="Refresh Garmin data cache.")
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
        help="Logging verbosity.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    run_fetch(since=args.since, full=args.full)


if __name__ == "__main__":
    main()
