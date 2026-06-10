"""Tests for natural-language due-date parsing."""

from datetime import date

import pytest

from todo.core.dates import parse_due_date

# Reference "today": Wednesday, 2026-06-10.
TODAY = date(2026, 6, 10)


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("today", date(2026, 6, 10)),
        ("EOD", date(2026, 6, 10)),
        ("end of day", date(2026, 6, 10)),
        ("tomorrow", date(2026, 6, 11)),
        ("EOW", date(2026, 6, 12)),  # Friday of this week
        ("end of week", date(2026, 6, 12)),
        ("EOM", date(2026, 6, 30)),
        ("EOY", date(2026, 12, 31)),
        ("in 3 days", date(2026, 6, 13)),
        ("next week", date(2026, 6, 17)),
        ("monday", date(2026, 6, 15)),  # upcoming Monday
        ("on friday", date(2026, 6, 12)),
        ("wednesday", date(2026, 6, 17)),  # bare weekday is always future
        ("next monday", date(2026, 6, 22)),  # a week beyond "monday"
        ("6/11", date(2026, 6, 11)),
        ("07/04/2026", date(2026, 7, 4)),
        ("2026-07-04", date(2026, 7, 4)),
        ("July 4", date(2026, 7, 4)),
        ("1/5", date(2027, 1, 5)),  # past this year -> rolls to next year
        ("due today", date(2026, 6, 10)),  # leading preposition stripped
        ("by 6/11", date(2026, 6, 11)),
    ],
)
def test_parse_due_date(expr, expected):
    assert parse_due_date(expr, today=TODAY) == expected


@pytest.mark.parametrize("expr", ["", "   ", "not a date", "asdfqwer"])
def test_parse_due_date_invalid(expr):
    with pytest.raises(ValueError):
        parse_due_date(expr, today=TODAY)


def test_explicit_year_not_rolled_forward():
    # A past date WITH an explicit year stays in that year.
    assert parse_due_date("01/05/2026", today=TODAY) == date(2026, 1, 5)


def test_defaults_to_real_today():
    # Smoke check that today=None path works (uses date.today()).
    assert isinstance(parse_due_date("today"), date)
