"""Larry Williams pattern detectors (articles 20510, 21063, 21127, 21391).

All detectors operate on **oldest-first** candle dict lists. They return
either a boolean (single-pattern check on the latest bars) or a list of
``Setup`` objects (full historical scan).

Patterns implemented:

- **Consecutive same-direction closes** (Part 9) — detect N closed bars in
  the same direction. Used both as a stand-alone signal and as a
  building block for the non-random tester.
- **Bearish outside-day with down close** (Part 9) — fade-the-extremes.
- **Uptrend with pullback** (Part 9) — Williams' two-lookback pullback
  definition (long-term up, short-term down).
- **Smash Day reversal** (Parts 10, 11, 12) — close beyond the prior N
  lows/highs that fails to follow through; trade triggers on next bar
  break of the smash bar's opposite extreme.
- **Hidden Smash Day reversal** (Parts 13, 14, 15) — close in the wrong
  quartile of its own range despite a directionally-aligned close vs the
  prior bar; same break-of-extreme confirmation.
"""

from __future__ import annotations

from typing import Any, Literal

from .bars import Candle, is_outside_bar
from .signals import Direction, Setup

CloseState = Literal["up", "down"]

# Default thresholds from the article series.
DEFAULT_HIDDEN_SMASH_QUARTILE_PCT: float = 25.0
DEFAULT_SMASH_LOOKBACK: int = 1
DEFAULT_CONSECUTIVE_BARS: int = 3
DEFAULT_UPTREND_LOOKBACK: int = 30
DEFAULT_PULLBACK_LOOKBACK: int = 9


# --- Consecutive closes --------------------------------------------------


def is_consecutive_close_state(
    candles: list[dict[str, Any]],
    bars_to_check: int,
    state: CloseState,
) -> bool:
    """Are the last ``bars_to_check`` closed bars all in ``state``?

    Mirrors the MQL5 ``IsConsecutiveBarCloseState`` helper. Uses Python
    forward indexing — the "last closed bar" is ``candles[-1]``; the bar
    before is ``candles[-2]``; etc.

    Returns ``False`` (not raises) on insufficient data. Empty bars
    (range == 0) count as failure.
    """
    if bars_to_check <= 0:
        raise ValueError("bars_to_check must be >= 1")
    if len(candles) < bars_to_check:
        return False
    for k in range(1, bars_to_check + 1):
        c = Candle.from_dict(candles[-k])
        if c.open == 0.0 or c.close == 0.0:
            return False
        if state == "up" and c.close <= c.open:
            return False
        if state == "down" and c.close >= c.open:
            return False
    return True


# --- Outside-day-down (Part 9) -------------------------------------------


def is_outside_day_down_close(candles: list[dict[str, Any]]) -> bool:
    """Bearish outside bar with a close below the prior low.

    All three conditions on the **most recent closed bar** ``c`` vs prior ``p``:

    1. Outside bar: ``c.high > p.high AND c.low < p.low``.
    2. Bearish close beyond prior low: ``c.close < p.low``.
    3. Bearish bar: ``c.close < c.open`` (the article also accepts
       ``open > close`` which is equivalent).
    """
    if len(candles) < 2:
        return False
    p = Candle.from_dict(candles[-2])
    c = Candle.from_dict(candles[-1])
    if not is_outside_bar(p, c):
        return False
    if c.close >= p.low:
        return False
    return c.is_bearish


# --- Uptrend with pullback (Part 9) --------------------------------------


def is_uptrend_with_pullback(
    candles: list[dict[str, Any]],
    *,
    uptrend_lookback: int = DEFAULT_UPTREND_LOOKBACK,
    pullback_lookback: int = DEFAULT_PULLBACK_LOOKBACK,
) -> bool:
    """Williams' two-lookback pullback definition (Part 9).

    Both must hold simultaneously on the **forming** bar's open vs prior
    closes:

    - **Uptrend**: ``open[0] > close[uptrend_lookback]`` (current price
      above the close from N bars ago).
    - **Pullback**: ``open[0] < close[pullback_lookback]`` (current price
      below the close from M bars ago, with M < N).

    The "current open" maps to ``candles[-1]["open"]`` in our forward
    convention; ``close[N]`` maps to ``candles[-1 - N]["close"]``.
    """
    if uptrend_lookback <= pullback_lookback:
        raise ValueError("uptrend_lookback must exceed pullback_lookback")
    if len(candles) <= uptrend_lookback:
        return False

    cur_open = float(candles[-1]["open"])
    far_close = float(candles[-1 - uptrend_lookback]["close"])
    near_close = float(candles[-1 - pullback_lookback]["close"])

    return cur_open > far_close and cur_open < near_close


# --- Smash Day (Parts 10, 11, 12) ----------------------------------------


def is_smash_day_buy_setup(
    candles: list[dict[str, Any]],
    *,
    lookback: int = DEFAULT_SMASH_LOOKBACK,
) -> bool:
    """The most recent closed bar qualifies as a buy-side smash bar.

    Conditions (mirrors ``MapBuySmashDayReversals`` in Part 11):

    1. Bar's close is **below** each of the prior ``lookback`` bars' lows.
    2. Bar is NOT an outside bar relative to the bar before it.

    A trade is only triggered when the **next** bar breaks above the
    smash bar's high (see :func:`smash_day_buy_confirmed`).
    """
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    if len(candles) < lookback + 1:
        return False
    smash = Candle.from_dict(candles[-1])

    for k in range(1, lookback + 1):
        prev_low = float(candles[-1 - k]["low"])
        if smash.close >= prev_low:
            return False

    # The "bar before the smash bar" is candles[-2]; outside-bar test compares
    # smash to that previous bar.
    prev_bar = Candle.from_dict(candles[-2])
    return not is_outside_bar(prev_bar, smash)


def is_smash_day_sell_setup(
    candles: list[dict[str, Any]],
    *,
    lookback: int = DEFAULT_SMASH_LOOKBACK,
) -> bool:
    """Mirror of :func:`is_smash_day_buy_setup` for sell setups.

    Smash close must exceed each of the prior ``lookback`` highs, and the
    smash bar must not be an outside bar.
    """
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    if len(candles) < lookback + 1:
        return False
    smash = Candle.from_dict(candles[-1])

    for k in range(1, lookback + 1):
        prev_high = float(candles[-1 - k]["high"])
        if smash.close <= prev_high:
            return False

    prev_bar = Candle.from_dict(candles[-2])
    return not is_outside_bar(prev_bar, smash)


def smash_day_buy_confirmed(candles: list[dict[str, Any]]) -> bool:
    """Did the bar after the buy-side smash bar close above the smash high?

    Use this when the most recent closed bar is the **confirmation bar**
    (i.e. the smash bar is at index -2).
    """
    if len(candles) < 2:
        return False
    smash = Candle.from_dict(candles[-2])
    confirm = Candle.from_dict(candles[-1])
    return confirm.close > smash.high


def smash_day_sell_confirmed(candles: list[dict[str, Any]]) -> bool:
    """Did the bar after the sell-side smash bar close below the smash low?"""
    if len(candles) < 2:
        return False
    smash = Candle.from_dict(candles[-2])
    confirm = Candle.from_dict(candles[-1])
    return confirm.close < smash.low


# --- Hidden Smash Day (Parts 13, 14, 15) ---------------------------------


def _close_position_pct(c: Candle) -> float:
    """Where the close sits inside the bar, expressed as a percentage of
    the bar's range. ``0`` = close at the low, ``100`` = close at the high.
    Returns ``50.0`` for a zero-range bar (neutral)."""
    rng = c.range
    if rng <= 0.0:
        return 50.0
    return (c.close - c.low) / rng * 100.0


def is_hidden_smash_buy_bar(
    candles: list[dict[str, Any]],
    *,
    quartile_pct: float = DEFAULT_HIDDEN_SMASH_QUARTILE_PCT,
    require_close_below_open: bool = False,
) -> bool:
    """Is the most recent closed bar a Hidden Smash Day buy candidate?

    Conditions (Part 13):

    1. ``close > prev_close`` — closed higher than the prior bar.
    2. Bar range > 0.
    3. Close in the **lower quartile** of its own range:
       ``close <= low + range * (quartile_pct / 100)``.
    4. (Optional, strictest) ``close < open`` — bearish bar despite the
       upward close vs prior bar.
    """
    if len(candles) < 2:
        return False
    smash = Candle.from_dict(candles[-1])
    prev = Candle.from_dict(candles[-2])
    if smash.close <= prev.close:
        return False
    if smash.range <= 0.0:
        return False
    if _close_position_pct(smash) > quartile_pct:
        return False
    return not (require_close_below_open and smash.close >= smash.open)


def is_hidden_smash_sell_bar(
    candles: list[dict[str, Any]],
    *,
    quartile_pct: float = DEFAULT_HIDDEN_SMASH_QUARTILE_PCT,
    require_close_above_open: bool = False,
) -> bool:
    """Mirror of :func:`is_hidden_smash_buy_bar` for sell setups."""
    if len(candles) < 2:
        return False
    smash = Candle.from_dict(candles[-1])
    prev = Candle.from_dict(candles[-2])
    if smash.close >= prev.close:
        return False
    if smash.range <= 0.0:
        return False
    if _close_position_pct(smash) < (100.0 - quartile_pct):
        return False
    return not (require_close_above_open and smash.close <= smash.open)


def hidden_smash_buy_confirmed(candles: list[dict[str, Any]]) -> bool:
    """Did the bar after the Hidden Smash buy bar close above its high?"""
    if len(candles) < 2:
        return False
    smash = Candle.from_dict(candles[-2])
    confirm = Candle.from_dict(candles[-1])
    return confirm.close > smash.high


def hidden_smash_sell_confirmed(candles: list[dict[str, Any]]) -> bool:
    """Did the bar after the Hidden Smash sell bar close below its low?"""
    if len(candles) < 2:
        return False
    smash = Candle.from_dict(candles[-2])
    confirm = Candle.from_dict(candles[-1])
    return confirm.close < smash.low


# --- Historical scans ----------------------------------------------------


def scan_smash_days(
    candles: list[dict[str, Any]],
    *,
    symbol: str,
    timeframe: str,
    lookback: int = DEFAULT_SMASH_LOOKBACK,
    confirmed_only: bool = True,
) -> list[Setup]:
    """Scan the candle history for Smash Day reversals.

    When ``confirmed_only`` is True (default), a setup is only emitted
    when the bar **after** the smash has closed beyond the smash bar's
    opposite extreme. The trigger price is set to the confirmation bar's
    close; ``range_basis`` is the smash bar's range.
    """
    setups: list[Setup] = []
    if len(candles) < lookback + 2:
        return setups

    # i indexes the smash bar; we need at least `lookback` bars before
    # and one bar after for confirmation.
    end = len(candles) - (1 if confirmed_only else 0)
    for i in range(lookback, end):
        smash = Candle.from_dict(candles[i])

        # Buy side
        all_below = all(smash.close < float(candles[i - k]["low"]) for k in range(1, lookback + 1))
        if all_below and not is_outside_bar(Candle.from_dict(candles[i - 1]), smash):
            confirmed = (i + 1 < len(candles)) and (float(candles[i + 1]["close"]) > smash.high)
            if (not confirmed_only) or confirmed:
                trigger_index = i + 1 if confirmed_only else i
                trigger = candles[trigger_index]
                setups.append(
                    _smash_setup(
                        symbol=symbol,
                        timeframe=timeframe,
                        direction="BUY",
                        smash_index=i,
                        smash=smash,
                        trigger_index=trigger_index,
                        trigger_time=int(trigger["time"]),
                        trigger_price=float(trigger["close"]),
                    )
                )
                continue

        # Sell side
        all_above = all(smash.close > float(candles[i - k]["high"]) for k in range(1, lookback + 1))
        if all_above and not is_outside_bar(Candle.from_dict(candles[i - 1]), smash):
            confirmed = (i + 1 < len(candles)) and (float(candles[i + 1]["close"]) < smash.low)
            if (not confirmed_only) or confirmed:
                trigger_index = i + 1 if confirmed_only else i
                trigger = candles[trigger_index]
                setups.append(
                    _smash_setup(
                        symbol=symbol,
                        timeframe=timeframe,
                        direction="SELL",
                        smash_index=i,
                        smash=smash,
                        trigger_index=trigger_index,
                        trigger_time=int(trigger["time"]),
                        trigger_price=float(trigger["close"]),
                    )
                )
    return setups


def scan_hidden_smash_days(
    candles: list[dict[str, Any]],
    *,
    symbol: str,
    timeframe: str,
    quartile_pct: float = DEFAULT_HIDDEN_SMASH_QUARTILE_PCT,
    require_close_vs_open: bool = False,
    confirmed_only: bool = True,
) -> list[Setup]:
    """Scan the candle history for Hidden Smash Day reversals."""
    setups: list[Setup] = []
    if len(candles) < 3:
        return setups

    end = len(candles) - (1 if confirmed_only else 0)
    for i in range(1, end):
        smash = Candle.from_dict(candles[i])
        prev = Candle.from_dict(candles[i - 1])

        if smash.range <= 0.0:
            continue

        # Buy candidate
        if smash.close > prev.close and _close_position_pct(smash) <= quartile_pct:
            if require_close_vs_open and smash.close >= smash.open:
                pass
            else:
                confirmed = (i + 1 < len(candles)) and (float(candles[i + 1]["close"]) > smash.high)
                if (not confirmed_only) or confirmed:
                    trigger_index = i + 1 if confirmed_only else i
                    trigger = candles[trigger_index]
                    setups.append(
                        _hidden_setup(
                            symbol=symbol,
                            timeframe=timeframe,
                            direction="BUY",
                            smash_index=i,
                            smash=smash,
                            trigger_index=trigger_index,
                            trigger_time=int(trigger["time"]),
                            trigger_price=float(trigger["close"]),
                        )
                    )
                    continue

        # Sell candidate
        if smash.close < prev.close and _close_position_pct(smash) >= (100.0 - quartile_pct):
            if require_close_vs_open and smash.close <= smash.open:
                continue
            confirmed = (i + 1 < len(candles)) and (float(candles[i + 1]["close"]) < smash.low)
            if (not confirmed_only) or confirmed:
                trigger_index = i + 1 if confirmed_only else i
                trigger = candles[trigger_index]
                setups.append(
                    _hidden_setup(
                        symbol=symbol,
                        timeframe=timeframe,
                        direction="SELL",
                        smash_index=i,
                        smash=smash,
                        trigger_index=trigger_index,
                        trigger_time=int(trigger["time"]),
                        trigger_price=float(trigger["close"]),
                    )
                )
    return setups


# --- Setup builders ------------------------------------------------------


def _smash_setup(
    *,
    symbol: str,
    timeframe: str,
    direction: Direction,
    smash_index: int,
    smash: Candle,
    trigger_index: int,
    trigger_time: int,
    trigger_price: float,
) -> Setup:
    return Setup(
        symbol=symbol,
        timeframe=timeframe,
        direction=direction,
        pattern="smash_day",
        trigger_index=trigger_index,
        trigger_time=trigger_time,
        trigger_price=trigger_price,
        range_basis=smash.range,
        reason=(
            f"Smash Day {direction} reversal: smash bar at index {smash_index} "
            f"closed past prior extreme then confirmed."
        ),
        extras={
            "smash_index": int(smash_index),
            "smash_high": round(smash.high, 5),
            "smash_low": round(smash.low, 5),
            "smash_close": round(smash.close, 5),
        },
    )


def _hidden_setup(
    *,
    symbol: str,
    timeframe: str,
    direction: Direction,
    smash_index: int,
    smash: Candle,
    trigger_index: int,
    trigger_time: int,
    trigger_price: float,
) -> Setup:
    return Setup(
        symbol=symbol,
        timeframe=timeframe,
        direction=direction,
        pattern="hidden_smash_day",
        trigger_index=trigger_index,
        trigger_time=trigger_time,
        trigger_price=trigger_price,
        range_basis=smash.range,
        reason=(
            f"Hidden Smash Day {direction}: close in wrong quartile of own range, "
            f"confirmed on next bar."
        ),
        extras={
            "smash_index": int(smash_index),
            "smash_high": round(smash.high, 5),
            "smash_low": round(smash.low, 5),
            "smash_close": round(smash.close, 5),
            "close_position_pct": round(_close_position_pct(smash), 2),
        },
    )
