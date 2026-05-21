"""Pessimistic bar-by-bar backtest engine for Larry Williams setups.

Design choices
--------------

- **Closed-bar entry, intra-bar fill.** When a setup's confirmation
  bar closes, the next bar opens the trade at its open price. The
  trade is then evaluated bar-by-bar until SL or TP is hit, or the
  hold-bars limit is reached.
- **Pessimistic SL/TP ordering.** When the same bar's high and low
  bracket *both* SL and TP, we count it as an SL hit. This matches the
  worst-case discipline used in the momentum-candle multi-month study
  and avoids inflating PF when intra-bar tick order is unknown.
- **R-based PnL only.** Trade outcomes are reported as R multiples (0
  for break-even, +rr for TP, -1 for SL). Currency PnL would require
  symbol-specific contract size, tick value, and FX conversion — out of
  scope for the analytical engine.
- **No slippage / spread modelling.** Same reasoning: not a paper
  trading sim, just a strategy validator.
- **One position at a time, magic-style.** New setups while a trade is
  open are queued / dropped per ``cap`` (default cap=1, drop new).

The engine is detector-agnostic. A "signal source" is any callable that
returns a list of ``Setup`` objects given a candle slice. Built-in
adapters wrap ``lw.patterns.scan_smash_days`` and
``lw.patterns.scan_hidden_smash_days``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from . import patterns
from .signals import Direction, Setup

DEFAULT_RR: float = 3.0
DEFAULT_HOLD_BARS: int = 30
DEFAULT_CAP: int = 1


SignalSource = Callable[[list[dict[str, Any]], str, str], list[Setup]]


# --- Result schemas -----------------------------------------------------


@dataclass(slots=True, frozen=True)
class Trade:
    """One simulated trade."""

    direction: Direction
    pattern: str
    entry_index: int
    entry_time: int
    entry_price: float
    sl: float
    tp: float
    rr_target: float
    exit_index: int
    exit_time: int
    exit_price: float
    exit_reason: Literal["tp", "sl", "timeout"]
    r_multiple: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "pattern": self.pattern,
            "entry_index": int(self.entry_index),
            "entry_time": int(self.entry_time),
            "entry_price": round(self.entry_price, 5),
            "sl": round(self.sl, 5),
            "tp": round(self.tp, 5),
            "rr_target": self.rr_target,
            "exit_index": int(self.exit_index),
            "exit_time": int(self.exit_time),
            "exit_price": round(self.exit_price, 5),
            "exit_reason": self.exit_reason,
            "r_multiple": round(self.r_multiple, 4),
        }


@dataclass(slots=True)
class BacktestResult:
    """Aggregate stats from a backtest run."""

    label: str
    symbol: str
    timeframe: str
    candle_count: int
    setup_count: int
    trades: list[Trade] = field(default_factory=list)

    def stats(self) -> dict[str, Any]:
        n = len(self.trades)
        if n == 0:
            return {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "timeouts": 0,
                "win_rate": 0.0,
                "expectancy_r": 0.0,
                "total_r": 0.0,
                "profit_factor": 0.0,
                "avg_win_r": 0.0,
                "avg_loss_r": 0.0,
                "max_drawdown_r": 0.0,
            }
        wins = [t for t in self.trades if t.exit_reason == "tp"]
        losses = [t for t in self.trades if t.exit_reason == "sl"]
        timeouts = [t for t in self.trades if t.exit_reason == "timeout"]
        total_r = sum(t.r_multiple for t in self.trades)
        gross_win = sum(t.r_multiple for t in wins) + sum(
            t.r_multiple for t in timeouts if t.r_multiple > 0
        )
        gross_loss = abs(
            sum(t.r_multiple for t in losses)
            + sum(t.r_multiple for t in timeouts if t.r_multiple < 0)
        )
        # Drawdown on the cumulative R curve.
        peak = 0.0
        cum = 0.0
        max_dd = 0.0
        for t in self.trades:
            cum += t.r_multiple
            peak = max(peak, cum)
            max_dd = min(max_dd, cum - peak)
        return {
            "trades": n,
            "wins": len(wins),
            "losses": len(losses),
            "timeouts": len(timeouts),
            "win_rate": round(len(wins) / n, 4),
            "expectancy_r": round(total_r / n, 4),
            "total_r": round(total_r, 4),
            "profit_factor": (
                round(gross_win / gross_loss, 4) if gross_loss > 0 else float("inf")
            ),
            "avg_win_r": round(sum(t.r_multiple for t in wins) / len(wins), 4)
            if wins
            else 0.0,
            "avg_loss_r": round(sum(t.r_multiple for t in losses) / len(losses), 4)
            if losses
            else 0.0,
            "max_drawdown_r": round(max_dd, 4),
        }

    def to_dict(self, include_trades: bool = True) -> dict[str, Any]:
        d: dict[str, Any] = {
            "label": self.label,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "candle_count": int(self.candle_count),
            "setup_count": int(self.setup_count),
            "stats": self.stats(),
        }
        if include_trades:
            d["trades"] = [t.to_dict() for t in self.trades]
        return d


# --- Trade simulation ---------------------------------------------------


def _simulate_trade(
    candles: list[dict[str, Any]],
    setup: Setup,
    *,
    entry_index: int,
    sl: float,
    tp: float,
    rr_target: float,
    hold_bars: int,
) -> Trade:
    """Walk forward bar-by-bar from ``entry_index`` until SL/TP/timeout."""
    entry_bar = candles[entry_index]
    entry_price = float(entry_bar["open"])
    last_index = min(entry_index + hold_bars, len(candles) - 1)

    for j in range(entry_index, last_index + 1):
        bar = candles[j]
        high = float(bar["high"])
        low = float(bar["low"])
        if setup.direction == "BUY":
            hit_sl = low <= sl
            hit_tp = high >= tp
        else:
            hit_sl = high >= sl
            hit_tp = low <= tp

        if hit_sl and hit_tp:
            # Pessimistic: SL wins on ambiguous bars.
            return Trade(
                direction=setup.direction,
                pattern=setup.pattern,
                entry_index=entry_index,
                entry_time=int(entry_bar["time"]),
                entry_price=entry_price,
                sl=sl,
                tp=tp,
                rr_target=rr_target,
                exit_index=j,
                exit_time=int(bar["time"]),
                exit_price=sl,
                exit_reason="sl",
                r_multiple=-1.0,
            )
        if hit_sl:
            return Trade(
                direction=setup.direction,
                pattern=setup.pattern,
                entry_index=entry_index,
                entry_time=int(entry_bar["time"]),
                entry_price=entry_price,
                sl=sl,
                tp=tp,
                rr_target=rr_target,
                exit_index=j,
                exit_time=int(bar["time"]),
                exit_price=sl,
                exit_reason="sl",
                r_multiple=-1.0,
            )
        if hit_tp:
            return Trade(
                direction=setup.direction,
                pattern=setup.pattern,
                entry_index=entry_index,
                entry_time=int(entry_bar["time"]),
                entry_price=entry_price,
                sl=sl,
                tp=tp,
                rr_target=rr_target,
                exit_index=j,
                exit_time=int(bar["time"]),
                exit_price=tp,
                exit_reason="tp",
                r_multiple=rr_target,
            )

    # Timeout: exit at last bar's close.
    last_bar = candles[last_index]
    exit_price = float(last_bar["close"])
    sl_distance = abs(entry_price - sl)
    if sl_distance == 0:
        r = 0.0
    elif setup.direction == "BUY":
        r = (exit_price - entry_price) / sl_distance
    else:
        r = (entry_price - exit_price) / sl_distance
    return Trade(
        direction=setup.direction,
        pattern=setup.pattern,
        entry_index=entry_index,
        entry_time=int(entry_bar["time"]),
        entry_price=entry_price,
        sl=sl,
        tp=tp,
        rr_target=rr_target,
        exit_index=last_index,
        exit_time=int(last_bar["time"]),
        exit_price=exit_price,
        exit_reason="timeout",
        r_multiple=r,
    )


# --- Setup -> levels translation ---------------------------------------


def _smash_levels(setup: Setup, rr: float) -> tuple[float, float, float]:
    """Return (entry, sl, tp) for a Smash / Hidden Smash setup.

    The structural SL is the smash bar's opposite extreme (low for buys,
    high for sells), already stashed in ``setup.extras``. Entry is the
    setup's ``trigger_price`` (the close of the confirmation bar); the
    actual fill happens at the **next** bar's open during simulation.
    """
    smash_low = float(setup.extras["smash_low"])
    smash_high = float(setup.extras["smash_high"])
    entry = float(setup.trigger_price)
    if setup.direction == "BUY":
        sl = smash_low
        sl_distance = entry - sl
        tp = entry + sl_distance * rr
    else:
        sl = smash_high
        sl_distance = sl - entry
        tp = entry - sl_distance * rr
    return entry, sl, tp


# --- Top-level runner ---------------------------------------------------


def run_backtest(
    candles: list[dict[str, Any]],
    *,
    label: str,
    symbol: str,
    timeframe: str,
    setups: list[Setup],
    rr: float = DEFAULT_RR,
    hold_bars: int = DEFAULT_HOLD_BARS,
    cap: int = DEFAULT_CAP,
) -> BacktestResult:
    """Run a backtest given pre-computed setups.

    Setups are entered on the bar **after** their ``trigger_index``
    (the confirmation bar) at that bar's open price. Concurrent setups
    are dropped while a trade is open (cap=1 default).
    """
    result = BacktestResult(
        label=label,
        symbol=symbol,
        timeframe=timeframe,
        candle_count=len(candles),
        setup_count=len(setups),
    )
    if not candles or not setups:
        return result

    # Simulate sequentially. Sort by trigger_index ascending so trades
    # are processed in chronological order.
    sorted_setups = sorted(setups, key=lambda s: s.trigger_index)
    open_trades: list[int] = []  # exit_index of currently-open trades

    for s in sorted_setups:
        entry_index = s.trigger_index + 1
        if entry_index >= len(candles):
            continue
        # Drop any setups whose entry bar is still inside an open trade.
        open_trades = [end for end in open_trades if end >= entry_index]
        if len(open_trades) >= cap:
            continue

        entry_price, sl, tp = _smash_levels(s, rr)
        if (s.direction == "BUY" and sl >= entry_price) or (
            s.direction == "SELL" and sl <= entry_price
        ):
            # Invalid stop side — skip rather than crash.
            continue

        trade = _simulate_trade(
            candles,
            s,
            entry_index=entry_index,
            sl=sl,
            tp=tp,
            rr_target=rr,
            hold_bars=hold_bars,
        )
        result.trades.append(trade)
        open_trades.append(trade.exit_index)
    return result


# --- Convenience: scan + backtest in one call --------------------------


def backtest_smash_day(
    candles: list[dict[str, Any]],
    *,
    label: str,
    symbol: str,
    timeframe: str,
    smash_lookback: int = patterns.DEFAULT_SMASH_LOOKBACK,
    rr: float = DEFAULT_RR,
    hold_bars: int = DEFAULT_HOLD_BARS,
    cap: int = DEFAULT_CAP,
) -> BacktestResult:
    """Scan for Smash Day setups and run a backtest in one pass."""
    sigs = patterns.scan_smash_days(
        candles,
        symbol=symbol,
        timeframe=timeframe,
        lookback=smash_lookback,
        confirmed_only=True,
    )
    return run_backtest(
        candles,
        label=label,
        symbol=symbol,
        timeframe=timeframe,
        setups=sigs,
        rr=rr,
        hold_bars=hold_bars,
        cap=cap,
    )


def backtest_hidden_smash_day(
    candles: list[dict[str, Any]],
    *,
    label: str,
    symbol: str,
    timeframe: str,
    quartile_pct: float = patterns.DEFAULT_HIDDEN_SMASH_QUARTILE_PCT,
    require_close_vs_open: bool = False,
    rr: float = DEFAULT_RR,
    hold_bars: int = DEFAULT_HOLD_BARS,
    cap: int = DEFAULT_CAP,
) -> BacktestResult:
    """Scan for Hidden Smash Day setups and run a backtest in one pass."""
    sigs = patterns.scan_hidden_smash_days(
        candles,
        symbol=symbol,
        timeframe=timeframe,
        quartile_pct=quartile_pct,
        require_close_vs_open=require_close_vs_open,
        confirmed_only=True,
    )
    return run_backtest(
        candles,
        label=label,
        symbol=symbol,
        timeframe=timeframe,
        setups=sigs,
        rr=rr,
        hold_bars=hold_bars,
        cap=cap,
    )
