"""Larry Williams non-random behaviour tester (article 20510 — Part 3).

This module implements the **statistical scaffolding** behind Williams'
claim that markets are not random: certain conditions on a closed bar
shift the probability of the next bar's direction away from 50%.

Eight test cases match the MQL5 ``ENUM_NON_RANDOM_TEST_MODE`` from the
article (translated to forward-indexed Python):

1. ``open_to_close_bias``   — every bar (baseline)
2. ``after_one_down``        — last closed bar is bearish
3. ``after_two_down``        — last two closed bars bearish
4. ``after_three_down``      — last three closed bars bearish
5. ``after_one_up``          — last closed bar is bullish
6. ``after_two_up``          — last two closed bars bullish
7. ``after_three_up``        — last three closed bars bullish
8. ``after_short_term_low``  — Larry Williams 3-bar short-term low signature

The original EA "trades" each event by simulating a one-bar buy entered at
the open of the bar **after** the trigger, exited at that bar's close.
This module reproduces that experiment without a broker connection: it
walks the candle list, records each event, and computes the conditional
probability that the *next* bar closes bullish.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from .bars import Candle
from .patterns import is_consecutive_close_state
from .structure import is_larry_williams_short_term_low

TestMode = Literal[
    "open_to_close_bias",
    "after_one_down",
    "after_two_down",
    "after_three_down",
    "after_one_up",
    "after_two_up",
    "after_three_up",
    "after_short_term_low",
]

ALL_MODES: tuple[TestMode, ...] = (
    "open_to_close_bias",
    "after_one_down",
    "after_two_down",
    "after_three_down",
    "after_one_up",
    "after_two_up",
    "after_three_up",
    "after_short_term_low",
)


# --- Per-bar predicates ---------------------------------------------------
#
# Each predicate receives the candle history *up to and including* the
# trigger bar (i.e. ``candles[: i + 1]``) and returns True when the
# trigger condition is satisfied.

PredicateFn = Callable[[list[dict[str, Any]]], bool]


def _always_true(_: list[dict[str, Any]]) -> bool:
    return True


def _after_n_state(n: int, state: Literal["up", "down"]) -> PredicateFn:
    def pred(window: list[dict[str, Any]]) -> bool:
        return is_consecutive_close_state(window, n, state)

    return pred


_PREDICATES: dict[TestMode, PredicateFn] = {
    "open_to_close_bias": _always_true,
    "after_one_down": _after_n_state(1, "down"),
    "after_two_down": _after_n_state(2, "down"),
    "after_three_down": _after_n_state(3, "down"),
    "after_one_up": _after_n_state(1, "up"),
    "after_two_up": _after_n_state(2, "up"),
    "after_three_up": _after_n_state(3, "up"),
    "after_short_term_low": is_larry_williams_short_term_low,
}


# --- Result schema --------------------------------------------------------


@dataclass(slots=True, frozen=True)
class TestResult:
    """Aggregate outcome of one test on one candle series."""

    mode: TestMode
    events: int  # number of trigger occurrences
    bullish_next: int  # how many had a bullish *next* bar
    bearish_next: int  # how many had a bearish *next* bar
    flat_next: int  # next bar closed exactly at its open
    total_pnl: float  # sum of (next.close - next.open) — proxy for buy-and-hold
    avg_pnl: float  # total_pnl / events (0.0 when events == 0)
    win_rate: float  # bullish_next / (bullish + bearish)  (0.0 when both 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "events": int(self.events),
            "bullish_next": int(self.bullish_next),
            "bearish_next": int(self.bearish_next),
            "flat_next": int(self.flat_next),
            "total_pnl": round(self.total_pnl, 5),
            "avg_pnl": round(self.avg_pnl, 6),
            "win_rate": round(self.win_rate, 4),
        }


# --- Single-mode runner --------------------------------------------------


def run_test(
    candles: list[dict[str, Any]],
    mode: TestMode,
) -> TestResult:
    """Run one non-random test against a candle series.

    Trigger events are evaluated on every closed bar at index ``i`` where
    the predicate has enough lookback. The "trade" is a one-bar long: open
    at ``candles[i+1].open`` and close at ``candles[i+1].close``.

    The forming bar (the very last entry) is excluded as a *trigger* but
    is allowed as the next-bar outcome of the second-to-last trigger.
    """
    if mode not in _PREDICATES:
        raise ValueError(f"unknown mode: {mode!r}")
    pred = _PREDICATES[mode]
    n = len(candles)
    if n < 4:
        return TestResult(mode, 0, 0, 0, 0, 0.0, 0.0, 0.0)

    events = 0
    bullish = 0
    bearish = 0
    flat = 0
    total_pnl = 0.0

    # The next-bar outcome must exist, so trigger window stops at n-2.
    for i in range(n - 1):
        window = candles[: i + 1]
        if not pred(window):
            continue
        nxt = Candle.from_dict(candles[i + 1])
        events += 1
        delta = nxt.close - nxt.open
        total_pnl += delta
        if delta > 0:
            bullish += 1
        elif delta < 0:
            bearish += 1
        else:
            flat += 1

    decided = bullish + bearish
    return TestResult(
        mode=mode,
        events=events,
        bullish_next=bullish,
        bearish_next=bearish,
        flat_next=flat,
        total_pnl=total_pnl,
        avg_pnl=(total_pnl / events) if events else 0.0,
        win_rate=(bullish / decided) if decided else 0.0,
    )


# --- All-modes runner ---------------------------------------------------


def run_all_tests(
    candles: list[dict[str, Any]],
    modes: tuple[TestMode, ...] | None = None,
) -> list[TestResult]:
    """Run every (or a chosen subset of) non-random test on the series.

    Returns a list ordered the same as the input ``modes`` tuple. The
    default ``modes=None`` runs all eight tests in canonical order.
    """
    selected = modes if modes is not None else ALL_MODES
    return [run_test(candles, m) for m in selected]
