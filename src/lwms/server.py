"""FastMCP server exposing 8 trading tools.

Tools (read-only):
    - get_account
    - get_symbol_price
    - get_candles_latest
    - get_positions

Tools (destructive):
    - place_market_order
    - modify_position
    - close_position
    - close_all_positions

Each destructive tool honours ``MT5_DRY_RUN`` (default on). The
.claude/hooks/live-trade-guard.sh hook adds a second layer of protection by
requiring a CONFIRM_LIVE token in the user prompt.
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP

from . import account, market, trade
from .client import ensure_initialized
from .lw import nonrandom as lw_nonrandom
from .lw import patterns as lw_patterns
from .lw import structure as lw_structure
from .lw import volatility as lw_volatility

log = logging.getLogger("lwms")

INSTRUCTIONS = """\
You are connected to a MetaTrader 5 trading account via MCP.

Workflow rules (always follow):
1. Call `get_account` before placing any trade to verify margin and trade_allowed.
2. Call `get_symbol_price` before placing orders to confirm the live price.
3. Call `get_positions` to find ticket numbers before modifying or closing.
4. The default symbol focus for this account is XAUUSD (gold).
5. Destructive tools (place_market_order, modify_position, close_position,
   close_all_positions) may run in dry-run mode. Inspect the response and
   relay the dry_run flag clearly to the user.

Volume conventions on this InstaForex demo:
- Min volume is typically 0.01 lots; step is 0.01.
- The server normalises volumes that fall outside the symbol limits.
- XAUUSD spreads are wider than majors; default deviation is 30 points.
"""

mcp: FastMCP = FastMCP("lwms", instructions=INSTRUCTIONS)


def _ensure() -> dict[str, Any] | None:
    """Return an error dict if MT5 is unreachable, else None."""
    if not ensure_initialized():
        return {"error": "MT5 terminal not connected. Start the MT5 terminal and log in."}
    return None


# --- read-only tools ------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True})
def get_account() -> dict[str, Any]:
    """Return current trading account info: balance, equity, profit, margin,
    leverage, currency, trade_allowed. Call before placing trades."""
    if (err := _ensure()) is not None:
        return err
    return account.get_account()


@mcp.tool(annotations={"readOnlyHint": True})
def get_symbol_price(symbol: str = "XAUUSD") -> dict[str, Any]:
    """Return latest tick for a symbol: bid, ask, last, volume, time, spread.
    Default symbol is XAUUSD (gold)."""
    if (err := _ensure()) is not None:
        return err
    return market.get_symbol_price(symbol)


@mcp.tool(annotations={"readOnlyHint": True})
def get_candles_latest(
    symbol: str = "XAUUSD",
    timeframe: str = "H1",
    count: int = 100,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Return the most recent OHLCV candles.

    Args:
        symbol: trading symbol, e.g. "XAUUSD".
        timeframe: M1, M5, M15, M30, H1, H4, D1, W1, MN1, etc.
        count: number of bars (1..5000). Default 100.
    """
    if (err := _ensure()) is not None:
        return err
    return market.get_candles_latest(symbol=symbol, timeframe=timeframe, count=count)


@mcp.tool(annotations={"readOnlyHint": True})
def get_positions(symbol: str | None = None) -> list[dict[str, Any]] | dict[str, Any]:
    """List currently open positions, optionally filtered by symbol.
    Returns ticket, type (BUY/SELL), volume, price_open, sl, tp, profit,
    magic, comment for each position."""
    if (err := _ensure()) is not None:
        return err
    return trade.get_positions(symbol)


# --- destructive tools ----------------------------------------------------


@mcp.tool(annotations={"destructiveHint": True})
def place_market_order(
    symbol: str,
    side: str,
    volume: float,
    sl: float | None = None,
    tp: float | None = None,
    deviation: int = 30,
    magic: int | None = None,
    comment: str = "",
) -> dict[str, Any]:
    """Place a BUY or SELL market order at the current price.

    Honours MT5_DRY_RUN. retcode 10009 = success.

    Args:
        symbol: e.g. "XAUUSD".
        side: "BUY" or "SELL".
        volume: lot size, e.g. 0.01.
        sl: stop loss price (absolute, not points).
        tp: take profit price (absolute, not points).
        deviation: max slippage in points; default 30.
        magic: order magic number for idempotency; defaults from MT5_MAGIC.
        comment: optional comment shown in MT5.
    """
    if (err := _ensure()) is not None:
        return err
    return trade.place_market_order(
        symbol=symbol,
        side=side,
        volume=volume,
        sl=sl,
        tp=tp,
        deviation=deviation,
        magic=magic,
        comment=comment,
    )


@mcp.tool(annotations={"destructiveHint": True})
def modify_position(
    ticket: int,
    sl: float | None = None,
    tp: float | None = None,
) -> dict[str, Any]:
    """Update SL and/or TP on an existing open position. Provide at least one."""
    if (err := _ensure()) is not None:
        return err
    return trade.modify_position(ticket=ticket, sl=sl, tp=tp)


@mcp.tool(annotations={"destructiveHint": True})
def close_position(ticket: int, volume: float | None = None) -> dict[str, Any]:
    """Close an open position fully (omit volume) or partially.
    Use get_positions to find the ticket number first."""
    if (err := _ensure()) is not None:
        return err
    return trade.close_position(ticket=ticket, volume=volume)


@mcp.tool(annotations={"destructiveHint": True})
def close_all_positions(symbol: str | None = None) -> dict[str, Any]:
    """Close every open position, optionally only those for ``symbol``.
    Returns a count and per-position results."""
    if (err := _ensure()) is not None:
        return err
    return trade.close_all_positions(symbol)


# --- Larry Williams strategy tools ---------------------------------------
#
# These tools run pure-Python detectors over candle dicts fetched via
# `market.get_candles_latest`. None of them place trades; they return
# either structured swing/setup lists or non-random statistical results.


def _fetch_or_error(
    symbol: str,
    timeframe: str,
    count: int,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Fetch candles or surface the error dict for the LW tools."""
    candles = market.get_candles_latest(symbol=symbol, timeframe=timeframe, count=count)
    if isinstance(candles, dict):
        return candles
    if not candles:
        return {"error": "no candles returned"}
    return candles


@mcp.tool(annotations={"readOnlyHint": True})
def lw_market_structure(
    symbol: str = "XAUUSD",
    timeframe: str = "H1",
    lookback: int = 500,
) -> dict[str, Any]:
    """Detect Larry Williams 3-tier swing structure (short / intermediate / long).

    Implements the indicator from the LW Market Secrets series (Part 1).

    Args:
        symbol: trading symbol (default XAUUSD).
        timeframe: bar timeframe (M5..D1).
        lookback: number of recent candles to scan (default 500).

    Returns:
        ``{"short_lows", "short_highs", "intermediate_lows",
        "intermediate_highs", "long_lows", "long_highs"}`` — each a list
        of ``{index, time, price, kind, tier}`` dicts ordered oldest-first.
    """
    if (err := _ensure()) is not None:
        return err
    res = _fetch_or_error(symbol, timeframe, int(lookback))
    if isinstance(res, dict):
        return res
    return lw_structure.find_market_structure(res).to_dict()


@mcp.tool(annotations={"readOnlyHint": True})
def lw_smash_day_setups(
    symbol: str = "XAUUSD",
    timeframe: str = "D1",
    lookback: int = 300,
    smash_lookback: int = 1,
    confirmed_only: bool = True,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Scan for Larry Williams Smash Day reversals (Parts 10, 11, 12).

    A smash bar closes beyond the prior N lows (buy) or highs (sell) and
    is not an outside bar; the trade triggers when the next bar closes
    past the smash bar's opposite extreme.

    Args:
        symbol: trading symbol.
        timeframe: bar timeframe — daily is the canonical use.
        lookback: candles to fetch for the scan.
        smash_lookback: prior bars the smash close must clear (default 1).
        confirmed_only: when True (default), only emit setups whose
            confirmation bar has already closed.
    """
    if (err := _ensure()) is not None:
        return err
    res = _fetch_or_error(symbol, timeframe, int(lookback))
    if isinstance(res, dict):
        return res
    setups = lw_patterns.scan_smash_days(
        res,
        symbol=symbol,
        timeframe=timeframe,
        lookback=int(smash_lookback),
        confirmed_only=bool(confirmed_only),
    )
    return [s.to_dict() for s in setups]


@mcp.tool(annotations={"readOnlyHint": True})
def lw_hidden_smash_day_setups(
    symbol: str = "XAUUSD",
    timeframe: str = "D1",
    lookback: int = 300,
    quartile_pct: float = 25.0,
    require_close_vs_open: bool = False,
    confirmed_only: bool = True,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Scan for Larry Williams Hidden Smash Day reversals (Parts 13, 14, 15).

    A Hidden Smash bar closes in the wrong quartile of its own range
    despite a directionally-aligned close vs the prior bar; trade
    triggers on next-bar break of the smash bar's opposite extreme.

    Args:
        symbol: trading symbol.
        timeframe: bar timeframe — daily is canonical.
        lookback: candles to fetch.
        quartile_pct: close-position threshold (default 25.0).
        require_close_vs_open: if True, also require the smash bar to be
            bearish (BUY setup) or bullish (SELL setup) — strictest mode.
        confirmed_only: only emit setups whose confirmation bar has closed.
    """
    if (err := _ensure()) is not None:
        return err
    res = _fetch_or_error(symbol, timeframe, int(lookback))
    if isinstance(res, dict):
        return res
    setups = lw_patterns.scan_hidden_smash_days(
        res,
        symbol=symbol,
        timeframe=timeframe,
        quartile_pct=float(quartile_pct),
        require_close_vs_open=bool(require_close_vs_open),
        confirmed_only=bool(confirmed_only),
    )
    return [s.to_dict() for s in setups]


@mcp.tool(annotations={"readOnlyHint": True})
def lw_volatility_breakout_levels(
    symbol: str = "XAUUSD",
    timeframe: str = "D1",
    model: str = "previous_range",
    buy_mult: float = 0.50,
    sell_mult: float = 0.50,
    stop_mult: float = 0.50,
) -> dict[str, Any]:
    """Project today's volatility breakout entry / stop levels.

    Implements Part 5 (``previous_range``) and Part 6 (``swing_based``)
    range models. The forming bar's open is the projection anchor.

    Args:
        symbol: trading symbol.
        timeframe: bar timeframe (D1 is canonical for the daily breakout).
        model: ``"previous_range"`` or ``"swing_based"``.
        buy_mult, sell_mult, stop_mult: range multipliers (default 0.50).

    Returns:
        ``{today_open, range_basis, buy_entry, sell_entry, long_stop,
        short_stop, model}``.
    """
    if (err := _ensure()) is not None:
        return err
    if model not in ("previous_range", "swing_based"):
        return {"error": f"unknown model: {model!r}"}
    needed = 5 if model == "swing_based" else 2
    res = _fetch_or_error(symbol, timeframe, max(needed, 10))
    if isinstance(res, dict):
        return res
    if len(res) < needed:
        return {"error": f"need at least {needed} candles for model={model}"}
    levels = lw_volatility.project_breakout_levels(
        res,
        model=model,  # type: ignore[arg-type]
        buy_mult=float(buy_mult),
        sell_mult=float(sell_mult),
        stop_mult=float(stop_mult),
    )
    return levels.to_dict()


@mcp.tool(annotations={"readOnlyHint": True})
def lw_nonrandom_test(
    symbol: str = "XAUUSD",
    timeframe: str = "D1",
    lookback: int = 1000,
    mode: str = "all",
) -> list[dict[str, Any]] | dict[str, Any]:
    """Run Larry Williams' non-random behaviour tests (Part 3).

    Eight test cases each measure how often the **next** bar closes
    bullish given a trigger condition on the current bar. A truly random
    market would converge to ~50% across every test; deviations are
    Williams' evidence of structural bias.

    Args:
        symbol: trading symbol.
        timeframe: bar timeframe — daily is canonical.
        lookback: candles to fetch (>= 200 recommended).
        mode: a specific test name (e.g. ``"after_one_down"``) or
            ``"all"`` (default) to run every test.

    Returns:
        List of ``TestResult`` dicts with ``events``, ``bullish_next``,
        ``bearish_next``, ``flat_next``, ``total_pnl``, ``avg_pnl``,
        ``win_rate``.
    """
    if (err := _ensure()) is not None:
        return err
    res = _fetch_or_error(symbol, timeframe, int(lookback))
    if isinstance(res, dict):
        return res

    if mode == "all":
        results = lw_nonrandom.run_all_tests(res)
    else:
        if mode not in lw_nonrandom.ALL_MODES:
            return {
                "error": (f"unknown mode {mode!r}; valid: {[*list(lw_nonrandom.ALL_MODES), 'all']}")
            }
        results = [lw_nonrandom.run_test(res, mode)]  # type: ignore[arg-type]
    return [r.to_dict() for r in results]


@mcp.tool(annotations={"readOnlyHint": True})
def lw_consecutive_close_check(
    symbol: str = "XAUUSD",
    timeframe: str = "D1",
    bars: int = 3,
    state: str = "down",
) -> dict[str, Any]:
    """Are the last ``bars`` closed candles all up or all down?

    Useful for triggering Williams' Part 9 strategies (consecutive bearish
    bars buy, consecutive bullish bars fade).

    Args:
        symbol: trading symbol.
        timeframe: bar timeframe.
        bars: how many trailing bars to check (default 3).
        state: ``"up"`` or ``"down"``.
    """
    if (err := _ensure()) is not None:
        return err
    if state not in ("up", "down"):
        return {"error": f"state must be 'up' or 'down', got {state!r}"}
    res = _fetch_or_error(symbol, timeframe, max(int(bars) + 5, 10))
    if isinstance(res, dict):
        return res
    flag = lw_patterns.is_consecutive_close_state(res, int(bars), state)  # type: ignore[arg-type]
    last = res[-int(bars) :] if len(res) >= int(bars) else res
    return {
        "match": bool(flag),
        "state": state,
        "bars_checked": int(bars),
        "last_bars": [
            {
                "time": int(c["time"]),
                "open": float(c["open"]),
                "close": float(c["close"]),
                "direction": "up"
                if c["close"] > c["open"]
                else "down"
                if c["close"] < c["open"]
                else "flat",
            }
            for c in last
        ],
    }


__all__ = ["mcp"]
