"""Tests for garmin_reporting.auth — two-step MFA login flow."""
from unittest.mock import MagicMock, patch
import pytest

from garmin_reporting.auth import login_with_tokens, begin_login, complete_login


class _FakeGarmin:
    """Minimal stand-in for garminconnect.Garmin."""

    def __init__(self, return_mfa=False):
        self._return_mfa = return_mfa
        self.resumed = False
        self._tokenstore = None

    def login(self, tokenstore=None):
        self._tokenstore = tokenstore
        if self._return_mfa:
            return ("needs_mfa", {"state": "abc"})
        return None  # success, tokens written

    def resume_login(self, state, code):
        self.resumed = True
        if code != "123456":
            raise ValueError("wrong code")


# ---- login_with_tokens -------------------------------------------------------

def test_login_with_tokens_returns_none_when_no_tokenstore(tmp_path, monkeypatch):
    monkeypatch.setattr("garmin_reporting.auth._TOKENSTORE", str(tmp_path / "nonexistent"))
    result = login_with_tokens()
    assert result is None


def test_login_with_tokens_returns_none_when_tokenstore_empty(tmp_path, monkeypatch):
    tokenstore = tmp_path / "tokens"
    tokenstore.mkdir()
    monkeypatch.setattr("garmin_reporting.auth._TOKENSTORE", str(tokenstore))
    result = login_with_tokens()
    assert result is None


def test_login_with_tokens_returns_none_when_login_raises(tmp_path, monkeypatch):
    tokenstore = tmp_path / "tokens"
    tokenstore.mkdir()
    (tokenstore / "token.json").write_text("{}")
    monkeypatch.setattr("garmin_reporting.auth._TOKENSTORE", str(tokenstore))

    with patch("garmin_reporting.auth.Garmin") as MockGarmin:
        instance = MagicMock()
        instance.login.side_effect = Exception("expired")
        MockGarmin.return_value = instance
        result = login_with_tokens()
    assert result is None


# ---- begin_login -------------------------------------------------------------

def test_begin_login_no_mfa(tmp_path, monkeypatch):
    monkeypatch.setattr("garmin_reporting.auth._TOKENSTORE", str(tmp_path / "tokens"))
    fake = _FakeGarmin(return_mfa=False)
    with patch("garmin_reporting.auth.Garmin", return_value=fake):
        client, mfa_state = begin_login("user@example.com", "password")
    assert client is fake
    assert mfa_state is None


def test_begin_login_with_mfa(tmp_path, monkeypatch):
    monkeypatch.setattr("garmin_reporting.auth._TOKENSTORE", str(tmp_path / "tokens"))
    fake = _FakeGarmin(return_mfa=True)
    with patch("garmin_reporting.auth.Garmin", return_value=fake):
        client, mfa_state = begin_login("user@example.com", "password")
    assert client is fake
    assert mfa_state == {"state": "abc"}


# ---- complete_login ----------------------------------------------------------

def test_complete_login_succeeds():
    fake = _FakeGarmin(return_mfa=True)
    result = complete_login(fake, {"state": "abc"}, "123456")
    assert result is fake
    assert fake.resumed is True


def test_complete_login_wrong_code():
    fake = _FakeGarmin(return_mfa=True)
    with pytest.raises(ValueError, match="wrong code"):
        complete_login(fake, {"state": "abc"}, "999999")
