"""Garmin Connect authentication and token cache management.

Credentials are loaded from the .env file (GARMIN_EMAIL, GARMIN_PASSWORD).
Tokens are cached in ~/.garminconnect/ and auto-refreshed — you only need to
log in interactively (possibly with MFA) on the very first run.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from garminconnect import Garmin

from config import TOKEN_STORE


def _load_credentials() -> tuple[str, str]:
    """Load credentials from .env; raise clearly if missing."""
    load_dotenv()
    email = os.getenv("GARMIN_EMAIL", "").strip()
    password = os.getenv("GARMIN_PASSWORD", "").strip()
    if not email or not password:
        raise ValueError(
            "GARMIN_EMAIL and GARMIN_PASSWORD must be set in your .env file.\n"
            "Copy .env.example to .env and fill in your credentials."
        )
    return email, password


def get_client() -> Garmin:
    """Return an authenticated Garmin client, reusing cached tokens when possible.

    On first run (no cached tokens) this will print a prompt for your Garmin
    email/password and, if MFA is enabled on your account, a one-time code.

    Subsequent runs reuse the stored tokens and refresh them automatically.
    """
    email, password = _load_credentials()

    tokenstore = str(TOKEN_STORE)
    client = Garmin(email, password, prompt_mfa=lambda: input("Enter Garmin MFA code: "))

    if Path(tokenstore).exists() and any(Path(tokenstore).iterdir()):
        try:
            client.login(tokenstore)
            return client
        except Exception:
            # Cached tokens rejected — fall through to fresh login.
            pass

    # Fresh login (first run or expired tokens).
    client.login(tokenstore)
    return client
