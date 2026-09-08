"""Parse natural-language repeat phrases into RFC 5545 RRULE strings.

Calendar events repeat via a single RRULE attached to the series master; Google
Calendar expands the occurrences server-side, so we store one local row plus its
rule rather than materializing every instance.

The grammar is intentionally small — the common cases a user types at the CLI:

    daily | every day
    weekly | every week | every monday | weekly on tuesday
    monthly | every month | monthly on the 10th
    yearly | annually | every year
    every 2 weeks | every 3 months            (interval)
    ... until 2026-12-31 | ... for 6 times    (bounds, optional suffix)

Anything it cannot parse returns ``None`` so the caller can surface an error
rather than silently dropping the recurrence.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

_WEEKDAYS = {
    "monday": "MO",
    "mon": "MO",
    "tuesday": "TU",
    "tue": "TU",
    "tues": "TU",
    "wednesday": "WE",
    "wed": "WE",
    "thursday": "TH",
    "thu": "TH",
    "thurs": "TH",
    "friday": "FR",
    "fri": "FR",
    "saturday": "SA",
    "sat": "SA",
    "sunday": "SU",
    "sun": "SU",
}

_FREQ_WORDS = {
    "daily": "DAILY",
    "day": "DAILY",
    "weekly": "WEEKLY",
    "week": "WEEKLY",
    "monthly": "MONTHLY",
    "month": "MONTHLY",
    "yearly": "YEARLY",
    "annually": "YEARLY",
    "year": "YEARLY",
}


def _parse_count_or_until(text: str) -> tuple[str | None, str | None]:
    """Extract an optional COUNT (``for N times``) or UNTIL (``until <date>``)."""
    count = re.search(r"\bfor\s+(\d+)\s+(?:times|occurrences)\b", text)
    if count:
        return f"COUNT={int(count.group(1))}", None
    until = re.search(r"\buntil\s+(\d{4}-\d{2}-\d{2})\b", text)
    if until:
        # RFC 5545 UTC form; date-only is widened to end-of-day.
        ymd = until.group(1).replace("-", "")
        return None, f"UNTIL={ymd}T235959Z"
    return None, None


def parse_recurrence(phrase: str, start_at: datetime) -> str | None:
    """Convert a repeat ``phrase`` into an ``RRULE:...`` string, or ``None``.

    ``start_at`` anchors month/weekday defaults: a bare ``monthly`` pins to the
    start day-of-month, a bare ``weekly`` to the start weekday — matching what a
    user means by "repeat this event monthly".
    """
    if not phrase:
        return None
    text = phrase.strip().lower()
    if text in {"none", "no", "once", "never"}:
        return None

    parts: list[str] = []

    interval_match = re.search(r"\bevery\s+(\d+)\s+(day|week|month|year)s?\b", text)
    interval = int(interval_match.group(1)) if interval_match else 1

    named_days = [_WEEKDAYS[w] for w in _WEEKDAYS if re.search(rf"\b{w}\b", text)]
    # Dedup while preserving order.
    named_days = list(dict.fromkeys(named_days))

    monthday_match = re.search(r"\bon (?:the )?(\d{1,2})(?:st|nd|rd|th)?\b", text)

    freq: str | None = None
    if interval_match:
        freq = _FREQ_WORDS.get(interval_match.group(2))
    else:
        for word, code in _FREQ_WORDS.items():
            if re.search(rf"\b{word}\b", text):
                freq = code
                break
    if freq is None and named_days:
        freq = "WEEKLY"  # "every monday"
    if freq is None:
        return None

    parts.append(f"FREQ={freq}")
    if interval > 1:
        parts.append(f"INTERVAL={interval}")

    if freq == "WEEKLY":
        days = named_days or [
            ["MO", "TU", "WE", "TH", "FR", "SA", "SU"][start_at.weekday()]
        ]
        parts.append("BYDAY=" + ",".join(days))
    elif freq == "MONTHLY":
        day = int(monthday_match.group(1)) if monthday_match else start_at.day
        parts.append(f"BYMONTHDAY={day}")

    count, until = _parse_count_or_until(text)
    if count:
        parts.append(count)
    elif until:
        parts.append(until)

    return "RRULE:" + ";".join(parts)
