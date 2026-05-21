"""Context filters for Larry Williams strategies.

- **Trade Day of the Week (TDW)** — gate trades to a configurable subset of
  weekdays. From article 20941 (Part 7). The MQL5 enum uses Sunday=0,
  Monday=1, ..., Saturday=6 because that matches ``MqlDateTime.day_of_week``.
  Python's ``datetime.weekday()`` uses Monday=0..Sunday=6, so we expose
  both conventions and translate internally.
- **Session window** — restrict to a [start, end] hour:minute range.
  From article 21003 (Part 8). The article's ``HH.MM`` decimal format is
  preserved as a parsing helper; modern callers should use ``time``
  objects directly.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timezone

# Python weekday() values: Mon=0 ... Sun=6.
_WEEKDAY_NAMES: tuple[str, ...] = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def parse_weekday(name: str) -> int:
    """Return the Python ``datetime.weekday()`` value for a weekday name.

    Case-insensitive; accepts both full names ("Monday") and three-letter
    abbreviations ("Mon"). Raises ``ValueError`` on unknown names.
    """
    n = name.strip().lower()
    for i, full in enumerate(_WEEKDAY_NAMES):
        if n == full or n == full[:3]:
            return i
    raise ValueError(f"unknown weekday: {name!r}")


def mql5_weekday_to_python(mql5_dow: int) -> int:
    """Translate MQL5 ``MqlDateTime.day_of_week`` (Sun=0..Sat=6) to
    Python's ``weekday()`` (Mon=0..Sun=6).
    """
    if not 0 <= mql5_dow <= 6:
        raise ValueError(f"mql5 day_of_week must be 0..6, got {mql5_dow}")
    # MQL5: Sun=0 Mon=1 Tue=2 Wed=3 Thu=4 Fri=5 Sat=6
    # Py:    Mon=0 Tue=1 Wed=2 Thu=3 Fri=4 Sat=5 Sun=6
    table = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
    return table[mql5_dow]


@dataclass(slots=True)
class TradeDayFilter:
    """Per-weekday allow-list. Days are stored as Python weekday ints
    (Monday=0..Sunday=6).
    """

    allowed: frozenset[int] = field(default_factory=lambda: frozenset(range(7)))

    @classmethod
    def from_names(cls, names: Iterable[str]) -> TradeDayFilter:
        return cls(allowed=frozenset(parse_weekday(n) for n in names))

    @classmethod
    def all_days(cls) -> TradeDayFilter:
        return cls(allowed=frozenset(range(7)))

    @classmethod
    def weekdays_only(cls) -> TradeDayFilter:
        return cls(allowed=frozenset({0, 1, 2, 3, 4}))

    def is_allowed(self, ts: int | datetime) -> bool:
        """Accepts either an epoch-seconds int (treated as UTC) or a
        ``datetime`` (naive treated as UTC, aware respected)."""
        if isinstance(ts, int):
            dt = datetime.fromtimestamp(ts, tz=UTC)
        elif ts.tzinfo is None:
            dt = ts.replace(tzinfo=UTC)
        else:
            dt = ts
        return dt.weekday() in self.allowed


# --- Session window ------------------------------------------------------


def parse_hhmm_decimal(value: float) -> time:
    """Parse the article's ``HH.MM`` decimal format (e.g. ``9.30`` ->
    09:30). Fractional part is treated as base-10 minutes after the dot,
    not as a fraction of an hour — matching the MQL5 ``ParseTime`` helper.

    Raises ``ValueError`` on out-of-range inputs.
    """
    if value < 0 or value >= 24:
        raise ValueError(f"HH.MM out of range: {value}")
    hours = int(value)
    minutes = round((value - hours) * 100)
    if minutes >= 60:
        raise ValueError(f"minutes part out of range in {value}")
    return time(hour=hours, minute=minutes)


@dataclass(slots=True)
class SessionWindow:
    """Inclusive [start, end] window in a fixed timezone (default UTC).

    Supports overnight windows (``start > end``). ``tzinfo`` defaults to
    UTC; pass ``timezone(timedelta(hours=...))`` for broker-server time.
    """

    start: time
    end: time
    tz: timezone = UTC

    def is_within(self, ts: int | datetime) -> bool:
        if isinstance(ts, int):
            dt = datetime.fromtimestamp(ts, tz=self.tz)
        elif ts.tzinfo is None:
            dt = ts.replace(tzinfo=self.tz)
        else:
            dt = ts.astimezone(self.tz)
        cur = dt.timetz().replace(tzinfo=None)
        # Same-day window: start <= end.
        if self.start <= self.end:
            return self.start <= cur <= self.end
        # Overnight window: e.g. 22:00 .. 06:00 next day.
        return cur >= self.start or cur <= self.end


# --- Composition convenience --------------------------------------------


@dataclass(slots=True)
class ContextFilter:
    """Bundle TDW + session into a single check."""

    tdw: TradeDayFilter | None = None
    session: SessionWindow | None = None

    def allows(self, ts: int | datetime) -> bool:
        if self.tdw is not None and not self.tdw.is_allowed(ts):
            return False
        return not (self.session is not None and not self.session.is_within(ts))
