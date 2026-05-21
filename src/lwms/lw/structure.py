"""Larry Williams swing-structure detector.

Ported from articles 20511 (indicator) and 20512 (EA) of the MQL5 series.

Three nested levels:

- **short-term**  — three-bar swing low/high (the foundation pattern)
- **intermediate-term** — short-term swing flanked by lower/higher short
  swings on both sides
- **long-term** — intermediate swing flanked by lower/higher intermediate
  swings on both sides

The Williams definition of a short-term swing low (forward indexing,
``i >= 1`` and ``i <= n-2``):

    low[i] < low[i-1]  AND  low[i] < low[i+1]

Plus two filters from the article-3 formalisation:

- the swing bar at ``i`` must NOT be an outside bar relative to ``i-1``
- the bar at ``i+1`` must NOT be an inside bar relative to the swing bar

Public API
----------
- ``find_short_term_swings`` — returns SwingPoint lists for highs and lows
- ``find_intermediate_swings`` — derives the next tier from short swings
- ``find_long_term_swings`` — derives the top tier from intermediate swings
- ``find_market_structure`` — convenience that runs all three tiers and
  returns a ``MarketStructure`` snapshot
- ``is_larry_williams_short_term_low`` — single-pattern detector matching
  the article-3 specification (used by the non-random tester)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .bars import Candle, is_inside_bar, is_outside_bar

SwingKind = Literal["high", "low"]
SwingTier = Literal["short", "intermediate", "long"]


@dataclass(slots=True, frozen=True)
class SwingPoint:
    """A single confirmed swing point."""

    index: int  # forward index into the candle list
    time: int  # epoch seconds
    price: float
    kind: SwingKind
    tier: SwingTier

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": int(self.index),
            "time": int(self.time),
            "price": round(self.price, 5),
            "kind": self.kind,
            "tier": self.tier,
        }


@dataclass(slots=True, frozen=True)
class MarketStructure:
    """Bundle of all three tiers detected on a candle series."""

    short_lows: list[SwingPoint]
    short_highs: list[SwingPoint]
    intermediate_lows: list[SwingPoint]
    intermediate_highs: list[SwingPoint]
    long_lows: list[SwingPoint]
    long_highs: list[SwingPoint]

    def latest(self, kind: SwingKind, tier: SwingTier) -> SwingPoint | None:
        """Most recent swing of the requested kind and tier (or None)."""
        bag = self._bag(kind, tier)
        return bag[-1] if bag else None

    def _bag(self, kind: SwingKind, tier: SwingTier) -> list[SwingPoint]:
        if tier == "short":
            return self.short_lows if kind == "low" else self.short_highs
        if tier == "intermediate":
            return self.intermediate_lows if kind == "low" else self.intermediate_highs
        return self.long_lows if kind == "low" else self.long_highs

    def to_dict(self) -> dict[str, Any]:
        return {
            "short_lows": [p.to_dict() for p in self.short_lows],
            "short_highs": [p.to_dict() for p in self.short_highs],
            "intermediate_lows": [p.to_dict() for p in self.intermediate_lows],
            "intermediate_highs": [p.to_dict() for p in self.intermediate_highs],
            "long_lows": [p.to_dict() for p in self.long_lows],
            "long_highs": [p.to_dict() for p in self.long_highs],
        }


# --- Short-term swing detection ------------------------------------------


def find_short_term_swings(
    candles: list[dict[str, Any]],
) -> tuple[list[SwingPoint], list[SwingPoint]]:
    """Detect short-term swing lows and highs (Williams 3-bar rule).

    Returns ``(lows, highs)``. Both lists are ordered oldest-first.
    The first and last bars cannot be swing points (they have only one
    neighbour) so the search starts at ``i = 1`` and stops at ``n - 2``.
    """
    n = len(candles)
    lows: list[SwingPoint] = []
    highs: list[SwingPoint] = []
    if n < 3:
        return lows, highs

    for i in range(1, n - 1):
        cur = candles[i]
        prv = candles[i - 1]
        nxt = candles[i + 1]

        if cur["low"] < prv["low"] and cur["low"] < nxt["low"]:
            lows.append(
                SwingPoint(
                    index=i,
                    time=int(cur["time"]),
                    price=float(cur["low"]),
                    kind="low",
                    tier="short",
                )
            )
        if cur["high"] > prv["high"] and cur["high"] > nxt["high"]:
            highs.append(
                SwingPoint(
                    index=i,
                    time=int(cur["time"]),
                    price=float(cur["high"]),
                    kind="high",
                    tier="short",
                )
            )
    return lows, highs


# --- Intermediate / long swing aggregation -------------------------------


def _aggregate_tier(
    seeds: list[SwingPoint],
    kind: SwingKind,
    out_tier: SwingTier,
) -> list[SwingPoint]:
    """Promote a swing list to the next tier.

    A point qualifies for the next tier when it sits between two same-kind
    seed points whose price is *less extreme* than itself:

    - For ``kind == "high"``: price must be **higher** than both neighbours.
    - For ``kind == "low"``: price must be **lower** than both neighbours.
    """
    if len(seeds) < 3:
        return []
    out: list[SwingPoint] = []
    for k in range(1, len(seeds) - 1):
        prev_p = seeds[k - 1].price
        cur_p = seeds[k].price
        next_p = seeds[k + 1].price
        if kind == "high" and cur_p > prev_p and cur_p > next_p:
            s = seeds[k]
            out.append(SwingPoint(s.index, s.time, s.price, "high", out_tier))
        elif kind == "low" and cur_p < prev_p and cur_p < next_p:
            s = seeds[k]
            out.append(SwingPoint(s.index, s.time, s.price, "low", out_tier))
    return out


def find_intermediate_swings(
    short_lows: list[SwingPoint],
    short_highs: list[SwingPoint],
) -> tuple[list[SwingPoint], list[SwingPoint]]:
    """Promote short-term swings to intermediate-term swings."""
    return (
        _aggregate_tier(short_lows, "low", "intermediate"),
        _aggregate_tier(short_highs, "high", "intermediate"),
    )


def find_long_term_swings(
    intermediate_lows: list[SwingPoint],
    intermediate_highs: list[SwingPoint],
) -> tuple[list[SwingPoint], list[SwingPoint]]:
    """Promote intermediate swings to long-term swings."""
    return (
        _aggregate_tier(intermediate_lows, "low", "long"),
        _aggregate_tier(intermediate_highs, "high", "long"),
    )


def find_market_structure(candles: list[dict[str, Any]]) -> MarketStructure:
    """One-shot 3-tier swing detection.

    Returns a :class:`MarketStructure` with all six lists populated. Empty
    lists when the input is too short for any tier.
    """
    sl, sh = find_short_term_swings(candles)
    il, ih = find_intermediate_swings(sl, sh)
    ll, lh = find_long_term_swings(il, ih)
    return MarketStructure(
        short_lows=sl,
        short_highs=sh,
        intermediate_lows=il,
        intermediate_highs=ih,
        long_lows=ll,
        long_highs=lh,
    )


# --- Article-3 strict short-term low/high --------------------------------
#
# This variant is the one used by the non-random tester (Part 3). It adds
# the outside-bar / inside-bar filters absent from the plain swing rule.


def is_larry_williams_short_term_low(candles: list[dict[str, Any]]) -> bool:
    """Detect a Larry Williams short-term low on the most recent 3 closed bars.

    Uses MQL5 reverse-time indexing to mirror the article. With Python
    forward indexing, the relevant bars are::

        bar3 = candles[-3]   # oldest  (MQL5 shift=3)
        bar2 = candles[-2]   # middle / candidate swing (MQL5 shift=2)
        bar1 = candles[-1]   # newest closed bar (MQL5 shift=1)

    Conditions (all must hold):

    1. ``bar2.low`` is the lowest of the three (swing low).
    2. ``bar2`` is NOT an outside bar relative to ``bar3``.
    3. ``bar1`` is NOT an inside bar relative to ``bar2``.
    """
    if len(candles) < 3:
        return False
    bar3 = Candle.from_dict(candles[-3])
    bar2 = Candle.from_dict(candles[-2])
    bar1 = Candle.from_dict(candles[-1])

    if not (bar2.low < bar1.low and bar2.low < bar3.low):
        return False
    if is_outside_bar(bar3, bar2):
        return False
    return not is_inside_bar(bar2, bar1)


def is_larry_williams_short_term_high(candles: list[dict[str, Any]]) -> bool:
    """Mirror of :func:`is_larry_williams_short_term_low` for highs."""
    if len(candles) < 3:
        return False
    bar3 = Candle.from_dict(candles[-3])
    bar2 = Candle.from_dict(candles[-2])
    bar1 = Candle.from_dict(candles[-1])

    if not (bar2.high > bar1.high and bar2.high > bar3.high):
        return False
    if is_outside_bar(bar3, bar2):
        return False
    return not is_inside_bar(bar2, bar1)
