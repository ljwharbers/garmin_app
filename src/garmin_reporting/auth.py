"""Garmin Connect authentication and token cache management.

Three entry points cover every caller:

  login_with_tokens()      — try the cached tokenstore; returns a client or None.
                             Used on app startup to skip the login form if tokens
                             are still valid.

  begin_login(email, pwd)  — start a fresh login.  Returns (client, None) on
                             success, or (client, mfa_state) when the account
                             requires a one-time code.

  complete_login(c, s, code) — supply the MFA code returned by begin_login.
                             Returns the authenticated client.

  get_client()             — CLI helper: tokens-first; falls back to loading
                             credentials from .env and prompting for MFA
                             interactively.  Not used by the GUI.

Tokens are cached in ~/.garminconnect/ (the garminconnect default) and are
typically valid for about a year — so the email/password are rarely re-entered.
Credentials are NEVER persisted by this module.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from garminconnect import Garmin

from garmin_reporting.config import TOKEN_STORE

logger = logging.getLogger(__name__)

_TOKENSTORE = str(TOKEN_STORE)


# ---------------------------------------------------------------------------
# Public API — used by the NiceGUI app
# ---------------------------------------------------------------------------

def login_with_tokens() -> "Garmin | None":
    """Try to authenticate using cached tokens.

    Returns an authenticated Garmin client if the cached tokens are still
    valid, or None if they are absent or expired (caller should show the
    login form).
    """
    if not Path(_TOKENSTORE).exists() or not any(Path(_TOKENSTORE).iterdir()):
        return None
    try:
        # Construct a minimal client — no credentials needed for token-only login.
        client = Garmin()
        client.login(_TOKENSTORE)
        logger.info("Authenticated via cached tokens.")
        return client
    except Exception as exc:
        logger.info("Cached tokens invalid or expired: %s", exc)
        return None


def begin_login(email: str, password: str) -> "tuple[Garmin, dict | None]":
    """Start a fresh login with email + password.

    Returns:
        (client, None)       — login succeeded; tokens saved to tokenstore.
        (client, mfa_state)  — account needs a one-time code.  Pass
                               mfa_state to complete_login() along with
                               the code.

    Raises:
        Exception — if the credentials are wrong or the network is down.
    """
    client = Garmin(email, password, return_on_mfa=True)
    result = client.login(_TOKENSTORE)

    # garminconnect signals MFA required by returning ("needs_mfa", state_dict).
    if isinstance(result, tuple) and len(result) == 2 and result[0] == "needs_mfa":
        logger.info("MFA required for %s.", email)
        return client, result[1]

    logger.info("Login succeeded for %s.", email)
    return client, None


def complete_login(client: "Garmin", mfa_state: dict, code: str) -> "Garmin":
    """Complete an MFA login by supplying the one-time code.

    Returns the authenticated client (same object, now with valid tokens).
    Raises on wrong code or network error.
    """
    client.resume_login(mfa_state, code)
    logger.info("MFA login completed.")
    return client


# ---------------------------------------------------------------------------
# CLI helper — not used by the GUI
# ---------------------------------------------------------------------------

def get_client() -> "Garmin":
    """Return an authenticated client for headless CLI usage.

    Tries cached tokens first.  If they are missing/expired, falls back to
    reading GARMIN_EMAIL / GARMIN_PASSWORD from .env and performing an
    interactive login (prompting for the MFA code on the terminal if needed).
    """
    # 1. Try tokens.
    client = login_with_tokens()
    if client is not None:
        return client

    # 2. Load credentials from .env.
    try:
        from dotenv import load_dotenv  # optional dep for CLI path
        load_dotenv()
    except ImportError:
        pass

    email = os.getenv("GARMIN_EMAIL", "").strip()
    password = os.getenv("GARMIN_PASSWORD", "").strip()
    if not email or not password:
        raise ValueError(
            "No valid cached tokens found and GARMIN_EMAIL / GARMIN_PASSWORD "
            "are not set.  Either log in via the app UI or set credentials in "
            "a .env file."
        )

    # 3. Interactive login with blocking MFA prompt (terminal only).
    cli_client = Garmin(
        email,
        password,
        prompt_mfa=lambda: input("Enter Garmin MFA code: "),
    )
    cli_client.login(_TOKENSTORE)
    return cli_client
