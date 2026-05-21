"""Bar / candle helpers shared across the LW package.

A "candle" is the dict shape returned by ``lwms.market.get_candles_latest``:

    {
        "time": int,          # epoch seconds
        "open": float,
        "high": float,
        "low": float,
        "close": float,
        "tick_volume": int,
        "spread": int,
        "real_volume": int,
    }

All functions here treat the input list as **oldest-first** (Python
convention). The MQL5 articles use reverse-time indexing (index 0 = newest);
``mql5_index`` and ``from_mql5_index`` translate between the two views so
the original Larry Williams pseudo-code is easy to follow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class Candle:
    """Typed view over a candle dict — useful when you want autocompletion."""

    time: int
    open: float
    high: float
    low: float
    close: float
    tick_volume: int = 0
    spread: int = 0
    real_volume: int = 0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Candle:
        return cls(
            time=int(d["time"]),
            open=float(d["open"]),
            high=float(d["high"]),
            low=float(d["low"]),
            close=float(d["close"]),
            tick_volume=int(d.get("tick_volume", 0)),
            spread=int(d.get("spread", 0)),
            real_volume=int(d.get("real_volume", 0)),
        )

    @property
    def range(self) -> float:
        """High minus low. Returns 0.0 for invalid bars."""
        return max(0.0, self.high - self.low)

    @property
    def body(self) -> float:
        """Absolute body size (|close - open|)."""
        return abs(self.close - self.open)

    @property
    def is_bullish(self) -> bool:
        """True when close > open (strict)."""
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        """True when close < open (strict)."""
        return self.close < self.open


def ohlc_arrays(
    candles: list[dict[str, Any]],
) -> tuple[list[float], list[float], list[float], list[float], list[int]]:
    """Split a candle list into (opens, highs, lows, closes, volumes).

    Useful when an algorithm wants array slicing rather than dict access.
    All five arrays preserve the original order (oldest-first).
    """
    opens = [float(c["open"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    closes = [float(c["close"]) for c in candles]
    vols = [int(c.get("tick_volume", 0)) for c in candles]
    return opens, highs, lows, closes, vols


def mql5_index(forward_index: int, total: int) -> int:
    """Convert a Python forward index (oldest=0) to MQL5 reverse index (newest=0).

    >>> mql5_index(0, 100)
    99
    >>> mql5_index(99, 100)
    0
    """
    if total <= 0:
        raise ValueError("total must be positive")
    if forward_index < 0 or forward_index >= total:
        raise IndexError(f"forward_index {forward_index} out of range for total {total}")
    return total - 1 - forward_index


def from_mql5_index(reverse_index: int, total: int) -> int:
    """Inverse of :func:`mql5_index`."""
    if total <= 0:
        raise ValueError("total must be positive")
    if reverse_index < 0 or reverse_index >= total:
        raise IndexError(f"reverse_index {reverse_index} out of range for total {total}")
    return total - 1 - reverse_index


def is_outside_bar(prev: Candle | dict[str, Any], cur: Candle | dict[str, Any]) -> bool:
    """``cur`` engulfs ``prev``: high higher AND low lower (strict).

    Used as a filter in Larry Williams structure detection (a swing bar that
    is also an outside bar is rejected).
    """
    p = prev if isinstance(prev, Candle) else Candle.from_dict(prev)
    c = cur if isinstance(cur, Candle) else Candle.from_dict(cur)
    return c.high > p.high and c.low < p.low


def is_inside_bar(prev: Candle | dict[str, Any], cur: Candle | dict[str, Any]) -> bool:
    """``cur`` is inside ``prev``: high lower AND low higher (strict).

    Used as a filter in Larry Williams structure detection (the bar
    immediately following the swing must NOT be an inside bar).
    """
    p = prev if isinstance(prev, Candle) else Candle.from_dict(prev)
    c = cur if isinstance(cur, Candle) else Candle.from_dict(cur)
    return c.high < p.high and c.low > p.low


def crossover(prev_close: float, cur_close: float, level: float) -> bool:
    """Detect a strict close-price cross **above** ``level``.

    Mirrors the MQL5 detector ``closes[1] <= level AND closes[0] > level``
    once translated to Python's forward-time indexing.
    """
    return prev_close <= level < cur_close


def crossunder(prev_close: float, cur_close: float, level: float) -> bool:
    """Detect a strict close-price cross **below** ``level``."""
    return prev_close >= level > cur_close
