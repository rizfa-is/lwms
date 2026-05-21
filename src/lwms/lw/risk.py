"""Stop-loss, take-profit, and position-sizing math.

Mirrors the three families used across the LW article series:

- **Stop-loss models**
  - ``structure``   — at the swing / smash bar's extreme (Parts 4, 8, 10, 13, 15)
  - ``range_pct``   — entry +/- range_basis * stop_mult (Parts 5-12)
  - ``atr``         — entry +/- ATR(period) * mult (Parts 13, 15)

- **Take-profit** — fixed risk:reward applied to entry-to-SL distance.

- **Position sizing**
  - ``legacy``     — risk_pct * balance / (contract_size * sl_distance)  (Parts 5-12)
  - ``broker``     — risk_pct * balance / loss_per_lot, snapped to broker
                    volume_step / volume_min / volume_max (Parts 13, 15);
                    loss_per_lot is provided by the caller (it would come
                    from ``mt5.order_calc_profit`` in production).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .signals import Direction

StopLossModel = Literal["structure", "range_pct", "atr"]
SizingModel = Literal["legacy", "broker", "fixed"]

DEFAULT_RR: float = 3.0
DEFAULT_STOP_MULT: float = 0.50
DEFAULT_ATR_PERIOD: int = 14
DEFAULT_ATR_MULT: float = 2.0
DEFAULT_RISK_PCT: float = 1.0
DEFAULT_FIXED_LOT: float = 0.10
DEFAULT_VOLUME_MIN: float = 0.01
DEFAULT_VOLUME_STEP: float = 0.01
DEFAULT_VOLUME_MAX: float = 100.0


@dataclass(slots=True, frozen=True)
class RiskPlan:
    """Computed risk levels for a setup."""

    entry: float
    sl: float
    tp: float
    rr: float
    sl_distance: float
    volume: float | None = None


# --- Stop loss ----------------------------------------------------------


def stop_loss_at_structure(
    direction: Direction,
    structure_price: float,
) -> float:
    """Place SL at a swing / smash bar's extreme. The caller picks the
    structural reference price (e.g. the smash bar's low for a buy)."""
    return float(structure_price)


def stop_loss_by_range_pct(
    direction: Direction,
    entry: float,
    range_basis: float,
    stop_mult: float = DEFAULT_STOP_MULT,
) -> float:
    """SL = entry +/- range_basis * stop_mult."""
    if range_basis < 0:
        raise ValueError("range_basis must be non-negative")
    if direction == "BUY":
        return entry - range_basis * stop_mult
    return entry + range_basis * stop_mult


def stop_loss_by_atr(
    direction: Direction,
    entry: float,
    atr: float,
    atr_mult: float = DEFAULT_ATR_MULT,
) -> float:
    """SL = entry +/- ATR * mult."""
    if atr < 0:
        raise ValueError("atr must be non-negative")
    if direction == "BUY":
        return entry - atr * atr_mult
    return entry + atr * atr_mult


# --- Take profit -------------------------------------------------------


def take_profit_by_rr(
    direction: Direction,
    entry: float,
    sl: float,
    rr: float = DEFAULT_RR,
) -> float:
    """TP at fixed risk:reward ratio applied to actual SL distance."""
    if rr <= 0:
        raise ValueError("rr must be positive")
    sl_distance = abs(entry - sl)
    if direction == "BUY":
        return entry + sl_distance * rr
    return entry - sl_distance * rr


# --- ATR (Wilder) -------------------------------------------------------


def wilder_atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = DEFAULT_ATR_PERIOD,
) -> float | None:
    """Latest Wilder ATR value. Returns ``None`` if insufficient data.

    The seed is the simple mean of TR over the first ``period`` bars
    starting at index 1 (so ``prev_close`` exists). Smoothing uses
    ``atr = (atr*(p-1) + tr) / p`` for subsequent bars. Mirrors the
    formula used by ``MC_WilderATR`` in the reference repo.
    """
    n = len(closes)
    if not (len(highs) == len(lows) == n):
        raise ValueError("highs, lows, closes must have equal length")
    if period <= 0:
        raise ValueError("period must be positive")
    if n <= period:
        return None

    trs: list[float] = []
    for i in range(1, period + 1):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    atr = sum(trs) / period

    for i in range(period + 1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        atr = (atr * (period - 1) + tr) / period
    return atr


# --- Position sizing ----------------------------------------------------


@dataclass(slots=True, frozen=True)
class VolumeConstraints:
    """Broker volume rules pulled from ``symbol_info``."""

    volume_min: float = DEFAULT_VOLUME_MIN
    volume_step: float = DEFAULT_VOLUME_STEP
    volume_max: float = DEFAULT_VOLUME_MAX


def normalize_volume(volume: float, c: VolumeConstraints) -> float:
    """Clamp + round-down to step (matches ``trade._normalize_volume``)."""
    v = max(c.volume_min, min(volume, c.volume_max))
    step = c.volume_step or DEFAULT_VOLUME_STEP
    steps = int(v / step)
    return round(steps * step, 8)


def size_legacy(
    *,
    balance: float,
    risk_pct: float,
    contract_size: float,
    sl_distance: float,
    constraints: VolumeConstraints | None = None,
) -> float:
    """Legacy per-trade sizing formula used in Parts 5-12.

    ``volume = (risk_pct/100 * balance) / (contract_size * sl_distance)``

    Returns 0.0 when sizing collapses (zero distance, zero balance, etc.)
    so the caller can reject the trade.
    """
    if balance <= 0 or risk_pct <= 0 or sl_distance <= 0 or contract_size <= 0:
        return 0.0
    risk_money = (risk_pct / 100.0) * balance
    raw = risk_money / (contract_size * sl_distance)
    return normalize_volume(raw, constraints or VolumeConstraints())


def size_broker(
    *,
    balance: float,
    risk_pct: float,
    loss_per_lot: float,
    constraints: VolumeConstraints | None = None,
) -> float:
    """Broker-aware sizing (Parts 13, 15).

    ``loss_per_lot`` is the loss in account currency for 1.0 lot, computed
    via ``mt5.order_calc_profit(order_type, symbol, 1.0, entry, sl)`` in
    production. This module stays MT5-free; the caller passes the value.
    """
    if balance <= 0 or risk_pct <= 0 or loss_per_lot <= 0:
        return 0.0
    risk_money = (risk_pct / 100.0) * balance
    raw = risk_money / loss_per_lot
    return normalize_volume(raw, constraints or VolumeConstraints())


# --- Plan composition ---------------------------------------------------


def build_risk_plan(
    *,
    direction: Direction,
    entry: float,
    sl: float,
    rr: float = DEFAULT_RR,
    volume: float | None = None,
) -> RiskPlan:
    """Compute the TP and bundle entry/sl/tp/rr/distance.

    Validates that the SL sits on the correct side of the entry
    (``sl < entry`` for BUY, ``sl > entry`` for SELL); raises
    ``ValueError`` otherwise.
    """
    if direction == "BUY" and sl >= entry:
        raise ValueError("BUY stop must be below entry")
    if direction == "SELL" and sl <= entry:
        raise ValueError("SELL stop must be above entry")
    tp = take_profit_by_rr(direction, entry, sl, rr)
    return RiskPlan(
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        sl_distance=abs(entry - sl),
        volume=volume,
    )
