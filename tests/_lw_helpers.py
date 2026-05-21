"""Synthetic candle helpers used across LW tests.

Avoids touching MT5 entirely; everything is OHLCV dicts in the same
shape returned by ``lwms.market.get_candles_latest``.
"""

from __future__ import annotations

from typing import Any


def make_candle(
    *,
    time: int,
    open: float,
    high: float,
    low: float,
    close: float,
    tick_volume: int = 1000,
) -> dict[str, Any]:
    return {
        "time": int(time),
        "open": float(open),
        "high": float(high),
        "low": float(low),
        "close": float(close),
        "tick_volume": int(tick_volume),
        "spread": 1,
        "real_volume": 0,
    }


def linear_series(n: int, start: float = 100.0, step: float = 1.0) -> list[dict[str, Any]]:
    """Monotonically rising candles with body == 1.0 and tiny wicks."""
    out = []
    base = start
    for i in range(n):
        out.append(
            make_candle(
                time=1_700_000_000 + i * 3600,
                open=base,
                high=base + step + 0.1,
                low=base - 0.1,
                close=base + step,
            )
        )
        base += step
    return out


def alternating_series(n: int, base: float = 100.0, body: float = 1.0) -> list[dict[str, Any]]:
    """Alternating up / down bars (used for non-random sanity checks)."""
    out = []
    for i in range(n):
        if i % 2 == 0:
            o, c = base, base + body
        else:
            o, c = base + body, base
        out.append(
            make_candle(
                time=1_700_000_000 + i * 3600,
                open=o,
                high=max(o, c) + 0.1,
                low=min(o, c) - 0.1,
                close=c,
            )
        )
    return out


def candles_from_ohlc(
    rows: list[tuple[float, float, float, float]],
    *,
    start_time: int = 1_700_000_000,
    step_seconds: int = 86400,
) -> list[dict[str, Any]]:
    """Build a candle list from explicit (open, high, low, close) tuples."""
    return [
        make_candle(
            time=start_time + i * step_seconds,
            open=o,
            high=h,
            low=lo,
            close=c,
        )
        for i, (o, h, lo, c) in enumerate(rows)
    ]
