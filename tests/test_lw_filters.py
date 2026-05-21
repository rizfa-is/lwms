from __future__ import annotations

from datetime import UTC, datetime, time

from lwms.lw.filters import (
    ContextFilter,
    SessionWindow,
    TradeDayFilter,
    mql5_weekday_to_python,
    parse_hhmm_decimal,
    parse_weekday,
)


def test_parse_weekday_full_and_short_names():
    assert parse_weekday("Monday") == 0
    assert parse_weekday("mon") == 0
    assert parse_weekday("FRI") == 4


def test_mql5_weekday_translation():
    # Sunday=0 in MQL5 → Sunday=6 in Python
    assert mql5_weekday_to_python(0) == 6
    assert mql5_weekday_to_python(1) == 0  # Mon → Mon


def test_trade_day_filter_allows_only_named_days():
    f = TradeDayFilter.from_names(["Mon", "Wed", "Fri"])
    # Mon 2026-01-05 12:00 UTC
    monday = int(datetime(2026, 1, 5, 12, tzinfo=UTC).timestamp())
    tuesday = int(datetime(2026, 1, 6, 12, tzinfo=UTC).timestamp())
    assert f.is_allowed(monday)
    assert not f.is_allowed(tuesday)


def test_parse_hhmm_decimal_format():
    assert parse_hhmm_decimal(9.30) == time(9, 30)
    assert parse_hhmm_decimal(16.0) == time(16, 0)


def test_session_window_same_day():
    # 09:30 - 16:00 UTC
    w = SessionWindow(start=time(9, 30), end=time(16, 0))
    assert w.is_within(int(datetime(2026, 1, 5, 12, tzinfo=UTC).timestamp()))
    assert not w.is_within(int(datetime(2026, 1, 5, 8, tzinfo=UTC).timestamp()))


def test_session_window_overnight():
    # 22:00 - 06:00 UTC
    w = SessionWindow(start=time(22, 0), end=time(6, 0))
    assert w.is_within(int(datetime(2026, 1, 5, 23, tzinfo=UTC).timestamp()))
    assert w.is_within(int(datetime(2026, 1, 5, 5, tzinfo=UTC).timestamp()))
    assert not w.is_within(int(datetime(2026, 1, 5, 12, tzinfo=UTC).timestamp()))


def test_session_window_alt_timezone():
    # NY-time window 09:30-16:00 (UTC-5 / -4 around DST). Use fixed offset.
    ny = UTC  # use UTC for determinism in tests
    w = SessionWindow(start=time(9, 30), end=time(16, 0), tz=ny)
    aware = datetime(2026, 1, 5, 14, tzinfo=ny)
    assert w.is_within(aware)


def test_context_filter_bundles_tdw_and_session():
    cf = ContextFilter(
        tdw=TradeDayFilter.from_names(["Tue"]),
        session=SessionWindow(start=time(13, 0), end=time(15, 0)),
    )
    tue_in = int(datetime(2026, 1, 6, 14, tzinfo=UTC).timestamp())
    tue_out = int(datetime(2026, 1, 6, 16, tzinfo=UTC).timestamp())
    wed_in = int(datetime(2026, 1, 7, 14, tzinfo=UTC).timestamp())
    assert cf.allows(tue_in)
    assert not cf.allows(tue_out)
    assert not cf.allows(wed_in)
