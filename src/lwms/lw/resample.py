"""Resample M1/M5 candles to higher timeframes.

The momentum-candle cache ships M5 candles with the standard schema:

    {time, open, high, low, close, tick_volume, spread, real_volume}

For Larry Williams strategies we usually want H1/H4/D1 bars. This module
aggregates a sorted oldest-first M5 list into the requested timeframe by
clustering on the bucket-aligned epoch second.

Bucket alignment uses **UTC**: a daily bar starts at 00:00 UTC, an H4 bar
at the nearest 4-hour boundary (00, 04, 08, 12, 16, 20), and so on.
This matches how MT5's ``copy_rates_from_pos`` returns its higher-TF bars
on InstaForex demo (broker server time is UTC).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

# Bucket size in seconds. Mirrors lwms.constants.TIMEFRAME_MAP keys but
# decoupled from MT5 so this module stays MT5-free.
BUCKET_SECONDS: dict[str, int] = {
    "M1": 60,
    "M2": 120,
    "M3": 180,
    "M4": 240,
    "M5": 300,
    "M6": 360,
    "M10": 600,
    "M12": 720,
    "M15": 900,
    "M20": 1200,
    "M30": 1800,
    "H1": 3600,
    "H2": 7200,
    "H3": 10800,
    "H4": 14400,
    "H6": 21600,
    "H8": 28800,
    "H12": 43200,
    "D1": 86400,
}


def _bucket_seconds(timeframe: str) -> int:
    key = timeframe.upper()
    if key not in BUCKET_SECONDS:
        raise ValueError(f"unsupported timeframe: {timeframe!r}")
    return BUCKET_SECONDS[key]


def _bucket_start(epoch: int, bucket: int) -> int:
    """Floor ``epoch`` to the bucket boundary."""
    return (epoch // bucket) * bucket


def resample(
    candles: Iterable[dict[str, Any]],
    timeframe: str,
) -> list[dict[str, Any]]:
    """Aggregate fine-grained candles to ``timeframe``.

    Args:
        candles: oldest-first iterable of candle dicts. Source timeframe
            must be smaller than ``timeframe`` (e.g. M5 -> H1) or the
            output mirrors the input.
        timeframe: target timeframe (M5, M15, H1, H4, D1, ...).

    Returns:
        New list of candle dicts (oldest-first). Volumes are summed,
        ``spread`` from the last child bar in each bucket is preserved.
    """
    bucket = _bucket_seconds(timeframe)
    out: list[dict[str, Any]] = []
    cur_start: int | None = None
    cur: dict[str, Any] | None = None

    for raw in candles:
        t = int(raw["time"])
        bs = _bucket_start(t, bucket)
        if cur is None or bs != cur_start:
            if cur is not None:
                out.append(cur)
            cur = {
                "time": bs,
                "open": float(raw["open"]),
                "high": float(raw["high"]),
                "low": float(raw["low"]),
                "close": float(raw["close"]),
                "tick_volume": int(raw.get("tick_volume", 0)),
                "spread": int(raw.get("spread", 0)),
                "real_volume": int(raw.get("real_volume", 0)),
            }
            cur_start = bs
        else:
            cur["high"] = max(cur["high"], float(raw["high"]))
            cur["low"] = min(cur["low"], float(raw["low"]))
            cur["close"] = float(raw["close"])
            cur["tick_volume"] += int(raw.get("tick_volume", 0))
            cur["real_volume"] += int(raw.get("real_volume", 0))
            cur["spread"] = int(raw.get("spread", cur["spread"]))

    if cur is not None:
        out.append(cur)
    return out
