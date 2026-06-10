"""AI parsing of natural-language event descriptions into structured drafts.

The model only *extracts* fields and the raw date/time phrases — it does NOT
compute absolute dates (small models are unreliable at weekday arithmetic).
The caller resolves the phrases deterministically via ``core.dates``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from .providers import ProviderManager

if TYPE_CHECKING:
    from datetime import datetime

    from ..models import AIProvider

EVENT_PARSE_PROMPT = """
You extract a single calendar event from a short natural-language description.
Extract fields literally — do NOT compute or resolve dates yourself.

- title: the event summary, with the date/time and invitee phrases removed.
- date_phrase: the date expression exactly as written (e.g. "friday",
  "next monday", "tomorrow", "june 12", "6/14"). Empty string if none given.
- time: the clock time exactly as written (e.g. "7pm", "noon", "9:30am",
  "14:30"). null if no specific time is given.
- end_time: the end clock time if given, else null.
- duration_minutes: the duration in minutes if stated (e.g. "for 90 minutes"),
  else null.
- location: the location if mentioned, else null.
- attendees: people to invite — tokens after "invite", "with", "for" — as
  lowercase aliases (e.g. "wife", "kids") or email addresses.

Do not invent details that are not present.
""".strip()


class EventDraft(BaseModel):
    """Fields extracted from a natural-language event description.

    Date/time are returned as raw phrases for deterministic resolution by the
    caller — never as computed absolute datetimes.
    """

    title: str = Field(..., description="Event title/summary")
    date_phrase: str = Field(
        "", description="Date expression as written, e.g. 'friday', 'tomorrow'"
    )
    time: str | None = Field(
        None, description="Clock time as written, e.g. '7pm'; null if none"
    )
    end_time: str | None = Field(None, description="End clock time if given")
    duration_minutes: int | None = Field(
        None, description="Duration in minutes if stated"
    )
    location: str | None = Field(None, description="Location if mentioned")
    attendees: list[str] = Field(
        default_factory=list,
        description="Aliases or emails to invite (e.g. wife, kids)",
    )


class EventParser:
    """Extract event fields from natural language using the AI provider."""

    def __init__(self) -> None:
        self.provider_manager = ProviderManager()

    async def parse(
        self,
        text: str,
        now: datetime,
        preferred_provider: AIProvider | None = None,
    ) -> EventDraft | None:
        """Extract an :class:`EventDraft` from ``text``.

        Args:
            text: The natural-language event description.
            now: Reference datetime (passed to the model for context only;
                date math is done by the caller).
            preferred_provider: Optional provider override.

        Returns:
            The extracted draft, or None if no provider is available or the
            call fails.
        """
        provider = await self.provider_manager.get_available_provider(
            preferred_provider
        )
        if not provider:
            return None

        prompt = f"{EVENT_PARSE_PROMPT}\n\nFor context, today is {now:%Y-%m-%d %A}."
        try:
            agent = await provider.create_agent(prompt, EventDraft)
            result = await agent.run(text)
            return result.output
        except Exception as e:  # pragma: no cover - network/provider errors
            print(f"Event parsing failed: {e}")
            return None
