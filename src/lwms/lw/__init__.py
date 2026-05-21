"""Larry Williams Market Secrets — Python port.

Concepts ported from the 15-part MQL5 series by Chacha Ian Maroa
(articles 20510-21393 on mql5.com). The MQL5 articles ship Expert
Advisors and indicators; this package extracts the *analytical core*
(detectors, filters, projections, risk math) into pure-Python functions
that operate on candle dicts produced by ``lwms.market.get_candles_latest``.

Module map
----------
- ``bars``       — candle dict helpers + bar utilities (new-bar, OHLC accessors)
- ``structure``  — 3-tier swing detector (short / intermediate / long term),
                    Larry Williams short-term low/high, outside / inside filters
- ``patterns``   — consecutive closes, uptrend-with-pullback, outside-day-down,
                    Smash Day reversals, Hidden Smash Day reversals
- ``volatility`` — yesterday-range and swing-based volatility breakout projections,
                    cross-over / cross-under triggers
- ``filters``    — Trade-Day-of-Week (TDW), session window
- ``risk``       — stop-loss models (structure / range-% / ATR), R:R take-profit,
                    position sizing (legacy + broker-aware)
- ``signals``    — ``Setup`` dataclass and composition helpers
- ``nonrandom``  — 8-case Larry Williams non-random behaviour tester (Part 3)

All public functions take type-hinted arguments and return dataclasses or
plain dicts. None of these modules import ``MetaTrader5`` — they work on
candle dicts only, so unit tests run anywhere.
"""

from __future__ import annotations

from .bars import Candle, ohlc_arrays
from .signals import Setup

__all__ = ["Candle", "Setup", "ohlc_arrays"]
