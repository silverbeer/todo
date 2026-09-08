"""Tests for parse_recurrence in src/todo/core/event_recurrence.py."""

from datetime import datetime

import pytest

from todo.core.event_recurrence import parse_recurrence

# Anchor datetimes used across tests.
# Friday the 10th — exercises both day-of-month=10 and weekday=FR in one anchor.
FRI_10 = datetime(2026, 1, 9, 10, 0)  # 2026-01-09 is a Friday; day=9, not 10
MON_1 = datetime(2026, 1, 5, 9, 0)  # Monday; day=5
FRI_10_DAY = datetime(2026, 6, 12, 19, 0)  # Friday the 12th — day=12

# Anchor used in the task spec examples: start day 10, weekday=Friday.
# 2026-01-16 is a Friday with day=16... Let's use a simpler, spec-matching anchor.
# The spec says start_at with day=10 and weekday matching "FR".
# 2026-05-08 is a Friday, day=8.  2026-05-15 is a Friday, day=15.
# 2026-01-09 is a Friday, day=9.
# We need a Friday whose day-of-month == 10: that would be e.g. 2026-04-10 (Friday).
SPEC_ANCHOR = datetime(2026, 4, 10, 9, 0)  # Friday, April 10 — day=10, weekday=FR


class TestNoneCases:
    def test_empty_string_returns_none(self):
        assert parse_recurrence("", SPEC_ANCHOR) is None

    def test_none_keyword_returns_none(self):
        assert parse_recurrence("none", SPEC_ANCHOR) is None

    def test_once_keyword_returns_none(self):
        assert parse_recurrence("once", SPEC_ANCHOR) is None

    def test_no_keyword_returns_none(self):
        assert parse_recurrence("no", SPEC_ANCHOR) is None

    def test_never_keyword_returns_none(self):
        assert parse_recurrence("never", SPEC_ANCHOR) is None

    def test_gibberish_returns_none(self):
        assert parse_recurrence("gibberish", SPEC_ANCHOR) is None

    def test_random_phrase_returns_none(self):
        assert parse_recurrence("pick up milk on the way home", SPEC_ANCHOR) is None


class TestDailyFrequency:
    def test_daily(self):
        assert parse_recurrence("daily", SPEC_ANCHOR) == "RRULE:FREQ=DAILY"

    def test_every_day(self):
        assert parse_recurrence("every day", SPEC_ANCHOR) == "RRULE:FREQ=DAILY"


class TestWeeklyFrequency:
    def test_weekly_uses_start_weekday(self):
        # SPEC_ANCHOR is a Friday -> BYDAY=FR
        assert parse_recurrence("weekly", SPEC_ANCHOR) == "RRULE:FREQ=WEEKLY;BYDAY=FR"

    def test_weekly_on_monday_start(self):
        anchor_mon = datetime(2026, 1, 5, 9, 0)  # Monday
        assert parse_recurrence("weekly", anchor_mon) == "RRULE:FREQ=WEEKLY;BYDAY=MO"

    def test_every_monday(self):
        assert (
            parse_recurrence("every monday", SPEC_ANCHOR)
            == "RRULE:FREQ=WEEKLY;BYDAY=MO"
        )

    def test_every_friday(self):
        assert (
            parse_recurrence("every friday", SPEC_ANCHOR)
            == "RRULE:FREQ=WEEKLY;BYDAY=FR"
        )

    def test_weekly_on_tuesday(self):
        assert (
            parse_recurrence("weekly on tuesday", SPEC_ANCHOR)
            == "RRULE:FREQ=WEEKLY;BYDAY=TU"
        )

    def test_every_week(self):
        assert (
            parse_recurrence("every week", SPEC_ANCHOR) == "RRULE:FREQ=WEEKLY;BYDAY=FR"
        )


class TestWeekdayAliases:
    """Short weekday aliases must all resolve to the correct two-letter code."""

    @pytest.mark.parametrize(
        "phrase,expected_byday",
        [
            ("every mon", "MO"),
            ("every tue", "TU"),
            ("every tues", "TU"),
            ("every wed", "WE"),
            ("every thu", "TH"),
            ("every thurs", "TH"),
            ("every fri", "FR"),
            ("every sat", "SA"),
            ("every sun", "SU"),
        ],
    )
    def test_weekday_alias(self, phrase, expected_byday):
        result = parse_recurrence(phrase, SPEC_ANCHOR)
        assert result == f"RRULE:FREQ=WEEKLY;BYDAY={expected_byday}"


class TestMonthlyFrequency:
    def test_monthly_on_the_10th(self):
        assert (
            parse_recurrence("monthly on the 10th", SPEC_ANCHOR)
            == "RRULE:FREQ=MONTHLY;BYMONTHDAY=10"
        )

    def test_monthly_uses_start_day(self):
        # SPEC_ANCHOR has day=10
        assert (
            parse_recurrence("monthly", SPEC_ANCHOR)
            == "RRULE:FREQ=MONTHLY;BYMONTHDAY=10"
        )

    def test_monthly_uses_start_day_other(self):
        anchor_15 = datetime(2026, 3, 15, 9, 0)
        assert (
            parse_recurrence("monthly", anchor_15) == "RRULE:FREQ=MONTHLY;BYMONTHDAY=15"
        )

    def test_every_month(self):
        assert (
            parse_recurrence("every month", SPEC_ANCHOR)
            == "RRULE:FREQ=MONTHLY;BYMONTHDAY=10"
        )

    def test_monthly_explicit_day_ordinal(self):
        # "on the 5th" should override the anchor day
        assert (
            parse_recurrence("monthly on the 5th", SPEC_ANCHOR)
            == "RRULE:FREQ=MONTHLY;BYMONTHDAY=5"
        )


class TestYearlyFrequency:
    def test_yearly(self):
        assert parse_recurrence("yearly", SPEC_ANCHOR) == "RRULE:FREQ=YEARLY"

    def test_annually(self):
        assert parse_recurrence("annually", SPEC_ANCHOR) == "RRULE:FREQ=YEARLY"

    def test_every_year(self):
        assert parse_recurrence("every year", SPEC_ANCHOR) == "RRULE:FREQ=YEARLY"


class TestIntervalFrequency:
    def test_every_2_weeks(self):
        # SPEC_ANCHOR is Friday -> BYDAY=FR, INTERVAL=2
        assert (
            parse_recurrence("every 2 weeks", SPEC_ANCHOR)
            == "RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=FR"
        )

    def test_every_3_months(self):
        # SPEC_ANCHOR has day=10
        assert (
            parse_recurrence("every 3 months", SPEC_ANCHOR)
            == "RRULE:FREQ=MONTHLY;INTERVAL=3;BYMONTHDAY=10"
        )

    def test_every_2_days(self):
        assert (
            parse_recurrence("every 2 days", SPEC_ANCHOR)
            == "RRULE:FREQ=DAILY;INTERVAL=2"
        )

    def test_every_2_years(self):
        assert (
            parse_recurrence("every 2 years", SPEC_ANCHOR)
            == "RRULE:FREQ=YEARLY;INTERVAL=2"
        )

    @pytest.mark.parametrize("n", [2, 3, 5, 10])
    def test_interval_value_preserved(self, n):
        result = parse_recurrence(f"every {n} weeks", SPEC_ANCHOR)
        assert f"INTERVAL={n}" in result


class TestUntilBound:
    def test_monthly_until(self):
        # SPEC_ANCHOR has day=10
        assert (
            parse_recurrence("monthly until 2026-12-31", SPEC_ANCHOR)
            == "RRULE:FREQ=MONTHLY;BYMONTHDAY=10;UNTIL=20261231T235959Z"
        )

    def test_weekly_until(self):
        result = parse_recurrence("weekly until 2026-06-30", SPEC_ANCHOR)
        assert result == "RRULE:FREQ=WEEKLY;BYDAY=FR;UNTIL=20260630T235959Z"

    def test_daily_until(self):
        result = parse_recurrence("daily until 2027-01-01", SPEC_ANCHOR)
        assert result == "RRULE:FREQ=DAILY;UNTIL=20270101T235959Z"

    def test_until_uses_utc_end_of_day_form(self):
        result = parse_recurrence("daily until 2026-12-25", SPEC_ANCHOR)
        assert result is not None
        assert "UNTIL=20261225T235959Z" in result


class TestCountBound:
    def test_weekly_for_6_times(self):
        assert (
            parse_recurrence("weekly for 6 times", SPEC_ANCHOR)
            == "RRULE:FREQ=WEEKLY;BYDAY=FR;COUNT=6"
        )

    def test_daily_for_30_occurrences(self):
        result = parse_recurrence("daily for 30 occurrences", SPEC_ANCHOR)
        assert result == "RRULE:FREQ=DAILY;COUNT=30"

    def test_monthly_for_3_times(self):
        result = parse_recurrence("monthly for 3 times", SPEC_ANCHOR)
        assert result == "RRULE:FREQ=MONTHLY;BYMONTHDAY=10;COUNT=3"

    @pytest.mark.parametrize("n", [1, 6, 12, 100])
    def test_count_value_preserved(self, n):
        result = parse_recurrence(f"weekly for {n} times", SPEC_ANCHOR)
        assert result is not None
        assert f"COUNT={n}" in result


class TestCountAndUntilMutualExclusion:
    def test_count_takes_precedence_when_both_present(self):
        # "for N times" is matched first in the implementation
        result = parse_recurrence("weekly for 4 times until 2026-12-31", SPEC_ANCHOR)
        assert result is not None
        assert "COUNT=4" in result
        assert "UNTIL=" not in result


class TestRrulePrefix:
    """Every successful parse must start with 'RRULE:'."""

    @pytest.mark.parametrize(
        "phrase",
        [
            "daily",
            "weekly",
            "monthly",
            "yearly",
            "every monday",
            "every 2 weeks",
            "monthly for 3 times",
            "daily until 2027-01-01",
        ],
    )
    def test_result_starts_with_rrule_prefix(self, phrase):
        result = parse_recurrence(phrase, SPEC_ANCHOR)
        assert result is not None
        assert result.startswith("RRULE:")


class TestCaseInsensitivity:
    def test_uppercase_phrase(self):
        assert parse_recurrence("DAILY", SPEC_ANCHOR) == "RRULE:FREQ=DAILY"

    def test_mixed_case(self):
        assert (
            parse_recurrence("Every Monday", SPEC_ANCHOR)
            == "RRULE:FREQ=WEEKLY;BYDAY=MO"
        )

    def test_weekly_mixed_case(self):
        assert parse_recurrence("Weekly", SPEC_ANCHOR) == "RRULE:FREQ=WEEKLY;BYDAY=FR"
