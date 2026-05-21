from __future__ import annotations

from lwms.lw import backtest, patterns

from ._lw_helpers import candles_from_ohlc


def _smash_buy_then_tp_series():
    """Engineer 5 sideways bars + 1 smash buy + 1 confirmation + 5 follow-through."""
    rows = [
        (100, 100.5, 99.5, 100.0),
        (100, 100.5, 99.5, 100.0),
        (100, 100.5, 99.5, 100.0),
        (100, 100.5, 99.5, 100.0),
        (100, 100.5, 99.5, 100.0),
        # Smash bar — closes below 99.5 prior low, smash_low = 98.5, smash_high = 99.4
        (99.0, 99.4, 98.5, 98.8),
        # Confirmation — closes > smash high (99.4)
        (98.5, 100.0, 98.5, 99.8),
        # Entry on this bar's open (next after confirmation).
        # Entry = open of bar 7 (100.0). SL = 98.5. distance = 1.5. TP at rr=3 -> 100 + 4.5 = 104.5.
        (100.0, 105.0, 99.9, 104.8),  # this bar's high (105) hits TP (104.5)
        (104.0, 105.0, 103.0, 104.0),
        (104.0, 105.0, 103.0, 104.0),
    ]
    return candles_from_ohlc(rows)


def _smash_buy_then_sl_series():
    rows = [
        (100, 100.5, 99.5, 100.0),
        (100, 100.5, 99.5, 100.0),
        (100, 100.5, 99.5, 100.0),
        (100, 100.5, 99.5, 100.0),
        (100, 100.5, 99.5, 100.0),
        (99.0, 99.4, 98.5, 98.8),
        (98.5, 100.0, 98.5, 99.8),
        # Entry at this bar's open ~100. SL=98.5 -> low<=98.5 hits SL.
        (100.0, 100.5, 98.0, 98.0),
    ]
    return candles_from_ohlc(rows)


def test_backtest_smash_day_records_winning_trade():
    candles = _smash_buy_then_tp_series()
    res = backtest.backtest_smash_day(
        candles,
        label="t",
        symbol="X",
        timeframe="D1",
        rr=3.0,
        hold_bars=10,
        cap=1,
    )
    assert res.setup_count == 1
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.direction == "BUY"
    assert t.exit_reason == "tp"
    assert t.r_multiple == 3.0


def test_backtest_smash_day_records_losing_trade():
    candles = _smash_buy_then_sl_series()
    res = backtest.backtest_smash_day(
        candles,
        label="t",
        symbol="X",
        timeframe="D1",
        rr=3.0,
        hold_bars=10,
    )
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "sl"
    assert t.r_multiple == -1.0


def test_backtest_stats_aggregate_correctly():
    # Mix one winner and one loser by chaining two scenarios.
    win = _smash_buy_then_tp_series()
    loss = _smash_buy_then_sl_series()
    # Make timelines disjoint by shifting times.
    shifted = []
    last_time = win[-1]["time"]
    for c in loss:
        copy = dict(c)
        copy["time"] = last_time + (c["time"] - loss[0]["time"]) + 86400
        shifted.append(copy)
    series = win + shifted
    res = backtest.backtest_smash_day(
        series, label="mixed", symbol="X", timeframe="D1", rr=3.0
    )
    stats = res.stats()
    assert stats["trades"] == 2
    assert stats["wins"] == 1
    assert stats["losses"] == 1
    assert stats["win_rate"] == 0.5
    # +3 - 1 = +2; expectancy = 1.0; PF = 3 / 1 = 3
    assert stats["total_r"] == 2.0
    assert stats["expectancy_r"] == 1.0
    assert stats["profit_factor"] == 3.0


def test_backtest_pessimistic_sl_priority():
    """When same bar brackets BOTH SL and TP, SL wins."""
    rows = [
        (100, 100.5, 99.5, 100.0),
        (99.0, 99.4, 98.5, 98.8),  # smash bar
        (98.5, 100.0, 98.5, 99.8),  # confirmation
        # Entry bar high=105 (TP) AND low=98.0 (SL) — pessimistic = SL.
        (100.0, 105.0, 98.0, 99.0),
    ]
    candles = candles_from_ohlc(rows)
    res = backtest.backtest_smash_day(
        candles, label="t", symbol="X", timeframe="D1", rr=3.0, hold_bars=5
    )
    assert len(res.trades) == 1
    assert res.trades[0].exit_reason == "sl"


def test_run_backtest_with_no_setups_returns_empty():
    res = backtest.run_backtest(
        [], label="empty", symbol="X", timeframe="D1", setups=[]
    )
    assert res.trades == []
    assert res.stats()["trades"] == 0


def test_backtest_hidden_smash_day_runs():
    # Build a series with one Hidden Smash buy + confirmation + follow-through.
    rows = [
        (100, 101, 99, 99.5),
        # Hidden Smash buy bar: close (100) > prev close (99.5), close in lower 25% of range.
        # range = 6, low = 99, close pos = (100-99)/6 = 16.7%. high = 105.
        (99.0, 105.0, 99.0, 100.0),
        # Confirmation: closes above smash high (105)
        (100.5, 106.0, 100.0, 105.5),
        # Entry at this bar's open. SL = smash low (99). distance = open-99.
        # TP at rr=3 must be reachable.
        (105.5, 120.0, 105.0, 119.0),
    ]
    candles = candles_from_ohlc(rows)
    sigs = patterns.scan_hidden_smash_days(
        candles, symbol="X", timeframe="D1", confirmed_only=True
    )
    assert len(sigs) >= 1
    res = backtest.backtest_hidden_smash_day(
        candles, label="hidden", symbol="X", timeframe="D1", rr=3.0
    )
    assert len(res.trades) >= 1
