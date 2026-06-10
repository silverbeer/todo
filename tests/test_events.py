"""Tests for the events + contacts data layer."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from todo.db.connection import DatabaseConnection
from todo.db.migrations import MigrationManager
from todo.db.repository import ContactRepository, EventRepository
from todo.models import EventStatus


@pytest.fixture
def db():
    """Temp database with schema + events tables initialized."""
    tmp = tempfile.mkdtemp()
    path = Path(tmp) / "events.db"
    conn = DatabaseConnection(str(path))
    mm = MigrationManager(conn)
    mm.initialize_schema()
    mm.ensure_events_schema()
    yield conn
    conn.close()
    if path.exists():
        path.unlink()
    Path(tmp).rmdir()


@pytest.fixture
def events(db):
    return EventRepository(db)


@pytest.fixture
def contacts(db):
    return ContactRepository(db)


class TestContactRepository:
    def test_add_and_get(self, contacts):
        contacts.add_contact("Wife", "jane@example.com")  # alias lowercased
        assert contacts.get_emails("wife") == ["jane@example.com"]

    def test_multi_email_alias(self, contacts):
        contacts.add_contact("kids", "sam@example.com")
        contacts.add_contact("kids", "alex@example.com")
        assert contacts.get_emails("kids") == ["alex@example.com", "sam@example.com"]

    def test_add_is_idempotent(self, contacts):
        contacts.add_contact("wife", "jane@example.com")
        contacts.add_contact("wife", "jane@example.com")
        assert contacts.get_emails("wife") == ["jane@example.com"]

    def test_list_contacts(self, contacts):
        contacts.add_contact("wife", "jane@example.com")
        contacts.add_contact("kids", "sam@example.com")
        assert contacts.list_contacts() == {
            "kids": ["sam@example.com"],
            "wife": ["jane@example.com"],
        }

    def test_resolve_mixes_aliases_and_emails_and_dedupes(self, contacts):
        contacts.add_contact("wife", "jane@example.com")
        contacts.add_contact("kids", "sam@example.com")
        contacts.add_contact("kids", "alex@example.com")
        resolved = contacts.resolve(
            ["wife", "kids", "extra@x.com", "jane@example.com", "unknown"]
        )
        # jane appears via alias and literal -> deduped; unknown alias -> nothing
        assert resolved == [
            "jane@example.com",
            "alex@example.com",
            "sam@example.com",
            "extra@x.com",
        ]

    def test_remove_alias(self, contacts):
        contacts.add_contact("kids", "sam@example.com")
        contacts.add_contact("kids", "alex@example.com")
        assert contacts.remove_alias("kids") == 2
        assert contacts.get_emails("kids") == []
        assert contacts.remove_alias("kids") == 0


class TestEventRepository:
    def test_create_and_get(self, events):
        ev = events.create_event(
            "Dinner",
            datetime(2026, 6, 12, 19, 0),
            location="Home",
            description="bring wine",
        )
        assert ev.id is not None
        fetched = events.get_by_id(ev.id)
        assert fetched.title == "Dinner"
        assert fetched.location == "Home"
        assert fetched.status == EventStatus.SCHEDULED
        assert fetched.is_synced is False
        assert fetched.attendees == []

    def test_attendees_roundtrip_and_dedup(self, events):
        ev = events.create_event("Party", datetime(2026, 6, 12, 19, 0))
        events.set_attendees(ev.id, ["a@x.com", "b@x.com", "a@x.com"])
        assert events.get_by_id(ev.id).attendees == ["a@x.com", "b@x.com"]
        # set replaces
        events.set_attendees(ev.id, ["c@x.com"])
        assert events.get_by_id(ev.id).attendees == ["c@x.com"]

    def test_list_upcoming_excludes_past_and_cancelled(self, events):
        events.create_event("Past", datetime(2020, 1, 1, 9, 0))
        events.create_event("Future", datetime(2099, 1, 1, 9, 0))
        cancelled = events.create_event("Cancelled", datetime(2099, 1, 2, 9, 0))
        events.cancel_event(cancelled.id)

        upcoming = events.list_events()
        titles = [e.title for e in upcoming]
        assert "Future" in titles
        assert "Past" not in titles
        assert "Cancelled" not in titles

        all_events = events.list_events(upcoming_only=False, include_cancelled=True)
        assert {"Past", "Future", "Cancelled"} <= {e.title for e in all_events}

    def test_cancel(self, events):
        ev = events.create_event("Meeting", datetime(2099, 1, 1, 9, 0))
        events.set_attendees(ev.id, ["a@x.com"])  # cancel works despite attendees
        cancelled = events.cancel_event(ev.id)
        assert cancelled.status == EventStatus.CANCELLED
        assert events.cancel_event(99999) is None

    def test_delete_removes_attendees(self, events, db):
        ev = events.create_event("Gone", datetime(2099, 1, 1, 9, 0))
        events.set_attendees(ev.id, ["a@x.com", "b@x.com"])
        assert events.delete_event(ev.id) is True
        assert events.get_by_id(ev.id) is None
        remaining = (
            db.connect()
            .execute("SELECT COUNT(*) FROM event_attendees WHERE event_id = ?", [ev.id])
            .fetchone()[0]
        )
        assert remaining == 0
        assert events.delete_event(ev.id) is False
