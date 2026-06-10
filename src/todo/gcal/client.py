"""Google Calendar client — one-way push of local events via gcsa.

gcsa (and the Google client libraries) are imported lazily so the rest of the
app, and the test suite, don't require them or any network/credentials.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.config import CalendarConfig
    from ..models import Event


class CalendarAuthError(RuntimeError):
    """Raised when Google Calendar auth is missing, invalid, or fails."""


class GoogleCalendarClient:
    """Thin wrapper over gcsa for pushing events to Google Calendar."""

    def __init__(self, config: CalendarConfig) -> None:
        self.calendar_id = config.calendar_id
        self.credentials_path = Path(config.credentials_path).expanduser()
        self.token_path = Path(config.token_path).expanduser()
        self._calendar = None  # cached gcsa GoogleCalendar

    # -- state ---------------------------------------------------------------

    def has_credentials(self) -> bool:
        """Whether the OAuth client credentials.json is present."""
        return self.credentials_path.exists()

    def is_authenticated(self) -> bool:
        """Whether an OAuth token has been stored (auth completed at least once)."""
        return self.token_path.exists()

    # -- connection ----------------------------------------------------------

    def _connect(self, *, open_browser: bool):
        """Return a connected gcsa GoogleCalendar, running the OAuth flow if needed."""
        if self._calendar is not None:
            return self._calendar
        if not self.has_credentials():
            raise CalendarAuthError(
                f"No OAuth credentials at {self.credentials_path}. Create a Google "
                "Cloud OAuth client (Desktop app), download credentials.json, and "
                "save it there (see 'todo calendar auth')."
            )
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from gcsa.google_calendar import GoogleCalendar

            self._calendar = GoogleCalendar(
                default_calendar=self.calendar_id,
                credentials_path=str(self.credentials_path),
                token_path=str(self.token_path),
                open_browser=open_browser,
            )
        except CalendarAuthError:
            raise
        except Exception as e:  # noqa: BLE001 - surface any auth/library failure
            raise CalendarAuthError(f"Google Calendar auth failed: {e}") from e
        return self._calendar

    def authenticate(self, *, open_browser: bool = True) -> None:
        """Run the OAuth flow (opening a browser if needed) and store the token."""
        self._connect(open_browser=open_browser)

    # -- event ops -----------------------------------------------------------

    def _to_gcsa_event(self, event: Event, *, with_attendees: bool):
        from gcsa.event import Event as GEvent

        if event.all_day:
            start = event.start_at.date()
            end = (event.end_at or event.start_at).date() + timedelta(days=1)
        else:
            start = event.start_at
            end = event.end_at or (event.start_at + timedelta(hours=1))
        return GEvent(
            event.title,
            start=start,
            end=end,
            description=event.description,
            location=event.location,
            attendees=list(event.attendees) if with_attendees else None,
            event_id=event.google_event_id,  # None on create, set on update
        )

    @staticmethod
    def _send_updates(send_invites: bool) -> str:
        # 'all' emails every guest; 'none' adds guests silently (no email).
        return "all" if send_invites else "none"

    def push_event(self, event: Event, *, send_invites: bool = False) -> str:
        """Create the event in Google Calendar; return its Google event id.

        Attendees are attached (and emailed) only when ``send_invites`` is True.
        """
        gc = self._connect(open_browser=False)
        created = gc.add_event(
            self._to_gcsa_event(event, with_attendees=send_invites),
            send_updates=self._send_updates(send_invites),
            calendar_id=self.calendar_id,
        )
        return created.event_id

    def update_event(self, event: Event, *, send_invites: bool = False) -> None:
        """Update an already-synced event; emails guests when ``send_invites``."""
        gc = self._connect(open_browser=False)
        gc.update_event(
            self._to_gcsa_event(event, with_attendees=send_invites),
            send_updates=self._send_updates(send_invites),
            calendar_id=self.calendar_id,
        )

    def delete_event(self, google_event_id: str) -> None:
        """Delete an event from Google Calendar by its Google event id."""
        gc = self._connect(open_browser=False)
        gc.delete_event(google_event_id, calendar_id=self.calendar_id)
