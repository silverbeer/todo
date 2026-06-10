"""Natural-language due-date parsing.

Turns expressions like ``today``, ``EOW``, ``next monday``, ``6/11`` into a
concrete :class:`datetime.date`. Keyword expressions are handled explicitly so
their semantics are predictable; anything else falls through to ``dateutil`` for
general date-format parsing.
"""

from __future__ import annotations

import calendar
import contextlib
import re
from datetime import date, datetime, timedelta

from dateutil import parser as _dateutil_parser

# Weekday name (and common abbreviations) -> Python weekday index (Mon=0).
_WEEKDAYS: dict[str, int] = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}


def _end_of_week(d: date) -> date:
    """End of week = Friday of the current week (rolls forward on Sat/Sun)."""
    return d + timedelta(days=(4 - d.weekday()) % 7)


def _end_of_month(d: date) -> date:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last_day)


def _weekday(d: date, target: int, *, following_week: bool) -> date:
    """Next occurrence of ``target`` weekday.

    A bare weekday name is always in the future (Monday-on-Monday means next
    Monday). ``following_week`` adds another week for "next <weekday>".
    """
    days = (target - d.weekday()) % 7
    if days == 0:
        days = 7
    if following_week:
        days += 7
    return d + timedelta(days=days)


def parse_due_date(text: str, today: date | None = None) -> date:
    """Parse a due-date expression into a concrete date.

    Supports keyword expressions — ``today``/``eod``, ``tomorrow``,
    ``eow``/``end of week`` (Friday), ``eom``/``end of month``,
    ``eoy``/``end of year``, weekday names (``monday``, ``on friday``),
    ``next <weekday>``, ``next week``, ``in N days`` — plus explicit dates in
    most formats via ``dateutil`` (``6/11``, ``07/04/2026``, ``2026-07-04``,
    ``July 4``). A bare month/day with no year that has already passed rolls to
    next year.

    Args:
        text: The expression to parse (leading ``due``/``on``/``by`` is ignored).
        today: Reference date; defaults to the current date.

    Returns:
        The resolved date.

    Raises:
        ValueError: If the expression cannot be parsed.
    """
    if today is None:
        today = date.today()
    if not text or not text.strip():
        raise ValueError("Empty due-date expression")

    s = re.sub(r"^(due|on|by)\s+", "", text.strip().lower()).strip()

    if s in ("today", "eod", "end of day"):
        return today
    if s in ("tomorrow", "tmrw", "tmr"):
        return today + timedelta(days=1)
    if s in ("eow", "end of week"):
        return _end_of_week(today)
    if s in ("eom", "end of month"):
        return _end_of_month(today)
    if s in ("eoy", "end of year"):
        return date(today.year, 12, 31)

    in_days = re.fullmatch(r"in\s+(\d+)\s+days?", s)
    if in_days:
        return today + timedelta(days=int(in_days.group(1)))

    nxt = re.fullmatch(r"next\s+(\w+)", s)
    if nxt:
        token = nxt.group(1)
        if token == "week":
            return today + timedelta(days=7)
        if token in _WEEKDAYS:
            return _weekday(today, _WEEKDAYS[token], following_week=True)

    if s in _WEEKDAYS:
        return _weekday(today, _WEEKDAYS[s], following_week=False)

    # Fall through to general date parsing for explicit dates.
    default_dt = datetime(today.year, today.month, today.day)
    try:
        parsed = _dateutil_parser.parse(s, default=default_dt).date()
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Could not parse due date: {text!r}") from exc

    # Roll a bare (yearless) month/day that already passed to next year.
    if parsed < today and not re.search(r"\d{4}", s):
        with contextlib.suppress(ValueError):  # e.g. Feb 29 -> leave as-is
            parsed = parsed.replace(year=parsed.year + 1)

    return parsed


def parse_datetime(text: str, now: datetime | None = None) -> datetime:
    """Parse an explicit date/time string into a :class:`datetime`.

    Used for the event ``--when`` flag (deterministic, no AI). Accepts most
    formats dateutil understands (``2026-06-12 19:00``, ``june 12 7pm``,
    ``7pm`` -> today at 19:00). Missing components default to ``now``.

    Raises:
        ValueError: If the string cannot be parsed.
    """
    if now is None:
        now = datetime.now()
    # Zero minute/second so an unspecified time ("7pm") doesn't inherit them
    # from "now"; an explicitly given minute ("9:30") is still respected.
    now = now.replace(minute=0, second=0, microsecond=0)
    if not text or not text.strip():
        raise ValueError("Empty date/time expression")
    try:
        return _dateutil_parser.parse(text.strip(), default=now)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Could not parse date/time: {text!r}") from exc
