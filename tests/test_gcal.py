"""Tests for the Google Calendar client (gcsa wrapper)."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from todo.core.config import CalendarConfig
from todo.gcal.client import CalendarAuthError, GoogleCalendarClient
from todo.models import Event


def _client(tmp: Path, *, creds: bool = True, token: bool = False):
    creds_p = tmp / "creds.json"
    token_p = tmp / "token.json"
    if creds:
        creds_p.write_text("{}")
    if token:
        token_p.write_text("{}")
    cfg = CalendarConfig(
        credentials_path=str(creds_p),
        token_path=str(token_p),
        calendar_id="primary",
    )
    return GoogleCalendarClient(cfg)


def test_auth_state_reflects_files(tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    c = _client(a, creds=True, token=False)
    assert c.has_credentials() is True
    assert c.is_authenticated() is False

    b = tmp_path / "b"
    b.mkdir()
    c2 = _client(b, creds=False, token=True)
    assert c2.has_credentials() is False
    assert c2.is_authenticated() is True


def test_connect_without_credentials_raises(tmp_path):
    c = _client(tmp_path, creds=False)
    with pytest.raises(CalendarAuthError):
        c.authenticate(open_browser=False)


def test_push_event_returns_google_id(tmp_path):
    c = _client(tmp_path, creds=True)
    fake_cal = Mock()
    fake_cal.add_event.return_value = Mock(event_id="g_123")
    with patch.object(c, "_connect", return_value=fake_cal):
        ev = Event(title="Dinner", start_at=datetime(2026, 6, 12, 19, 0))
        gid = c.push_event(ev)
    assert gid == "g_123"
    fake_cal.add_event.assert_called_once()


def test_delete_event_calls_gcsa(tmp_path):
    c = _client(tmp_path, creds=True)
    fake_cal = Mock()
    with patch.object(c, "_connect", return_value=fake_cal):
        c.delete_event("g_123")
    fake_cal.delete_event.assert_called_once_with("g_123", calendar_id="primary")


def test_all_day_event_uses_dates(tmp_path):
    c = _client(tmp_path, creds=True)
    ev = Event(title="Vacation", start_at=datetime(2026, 6, 20, 0, 0), all_day=True)
    gevent = c._to_gcsa_event(ev)
    # gcsa stores all-day events with date (not datetime) start/end
    assert not isinstance(gevent.start, datetime)
