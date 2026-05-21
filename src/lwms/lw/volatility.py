"""Larry Williams volatility-breakout projections (articles 20745, 20862).

Two range models:

- **Yesterday's range** (Part 5)
   ``range = high[1] - low[1]``  (the immediately prior closed bar)

- **Swing-based dominant range** (Part 6)
   ``swingA = |high[4] - low[1]|``  (high 3-back to yesterday's low)
   ``swingB = |high[2] - low[4]|``  (high 1-back to low 3-back)
   ``range  = max(swingA, swingB)``

Indices are MQL5 reverse-time (newest=0). With Python forward indexing:

  bar1 = candles[-2]   # yesterday / previous closed bar
  bar2 = candles[-3]
  bar3 = candles[-4]
  bar4 = candles[-5]   # 3 days ago

The "today open" is ``candles[-1]["open"]`` — the open of the **forming**
or most recently opened bar.

Projection levels (long convention; sell mirror in caller):

  buy_entry  = today_open + range * buy_mult
  sell_entry = today_open - range * sell_mult
  long_sl    = buy_entry  - range * stop_mult
  short_sl   = sell_entry + range * stop_mult
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

# Defaults from the article series.
DEFAULT_BUY_MULT: float = 0.50
DEFAULT_SELL_MULT: float = 0.50
DEFAULT_STOP_MULT: float = 0.50

VolatilityModel = Literal["previous_range", "swing_based"]


@dataclass(slots=True, frozen=True)
class BreakoutLevels:
    """Projected entry / stop levels for a volatility breakout day."""

    today_open: float
    range_basis: float
    buy_entry: float
    sell_entry: float
    long_stop: float
    short_stop: float
    model: VolatilityModel

    def to_dict(self) -> dict[str, Any]:
        return {
            "today_open": round(self.today_open, 5),
            "range_basis": round(self.range_basis, 5),
            "buy_entry": round(self.buy_entry, 5),
            "sell_entry": round(self.sell_entry, 5),
            "long_stop": round(self.long_stop, 5),
            "short_stop": round(self.short_stop, 5),
            "model": self.model,
        }


def previous_range(candles: list[dict[str, Any]]) -> float:
    """``high[1] - low[1]`` in MQL5 terms — yesterday's range."""
    if len(candles) < 2:
        raise ValueError("need at least 2 candles")
    prev = candles[-2]
    return float(prev["high"]) - float(prev["low"])


def swing_dominant_range(candles: list[dict[str, Any]]) -> float:
    """Larger of the two 3-day swing distances (Part 6).

    ``swingA = |high[4] - low[1]|``  (3-back high to 1-back low)
    ``swingB = |high[2] - low[4]|``  (1-back high to 3-back low)
    ``range  = max(swingA, swingB)``
    """
    if len(candles) < 5:
        raise ValueError("need at least 5 candles for swing-based range")
    bar1 = candles[-2]
    bar2 = candles[-3]
    bar4 = candles[-5]
    swing_a = abs(float(bar4["high"]) - float(bar1["low"]))
    swing_b = abs(float(bar2["high"]) - float(bar4["low"]))
    return max(swing_a, swing_b)


def project_breakout_levels(
    candles: list[dict[str, Any]],
    *,
    model: VolatilityModel = "previous_range",
    buy_mult: float = DEFAULT_BUY_MULT,
    sell_mult: float = DEFAULT_SELL_MULT,
    stop_mult: float = DEFAULT_STOP_MULT,
) -> BreakoutLevels:
    """Compute entry + stop levels for the forming day's breakout setup.

    The forming bar's open is ``candles[-1]["open"]``.
    """
    if len(candles) < 2:
        raise ValueError("need at least 2 candles")

    today_open = float(candles[-1]["open"])
    if model == "previous_range":
        rng = previous_range(candles)
    elif model == "swing_based":
        rng = swing_dominant_range(candles)
    else:
        raise ValueError(f"unknown model: {model!r}")

    buy_entry = today_open + rng * buy_mult
    sell_entry = today_open - rng * sell_mult
    return BreakoutLevels(
        today_open=today_open,
        range_basis=rng,
        buy_entry=buy_entry,
        sell_entry=sell_entry,
        long_stop=buy_entry - rng * stop_mult,
        short_stop=sell_entry + rng * stop_mult,
        model=model,
    )
