from __future__ import annotations

from lwms.lw import patterns

from ._lw_helpers import candles_from_ohlc, make_candle


def test_consecutive_down_closes_true():
    series = [make_candle(time=i, open=10, high=10.5, low=9, close=9.5) for i in range(3)]
    assert patterns.is_consecutive_close_state(series, 3, "down")


def test_consecutive_up_closes_false_when_one_down():
    series = [
        make_candle(time=0, open=10, high=11, low=9.5, close=10.5),
        make_candle(time=1, open=10, high=11, low=9.5, close=10.5),
        make_candle(time=2, open=10, high=11, low=9.5, close=9.6),  # down
    ]
    assert not patterns.is_consecutive_close_state(series, 3, "up")


def test_outside_day_down_close():
    series = candles_from_ohlc(
        [
            (10, 11, 9.5, 10.5),
            (10.5, 12, 8, 8.5),  # outside, bearish, close < prior low
        ]
    )
    assert patterns.is_outside_day_down_close(series)


def test_outside_day_down_close_rejects_when_close_above_prior_low():
    series = candles_from_ohlc(
        [
            (10, 11, 9.5, 10.5),
            (10.5, 12, 8, 9.6),  # bearish but close >= prior low (9.5)
        ]
    )
    assert not patterns.is_outside_day_down_close(series)


def test_uptrend_with_pullback_basic():
    # 35 bars: long-term up, recent pullback within last 10 bars.
    rows: list[tuple[float, float, float, float]] = []
    base = 100.0
    for _ in range(25):
        rows.append((base, base + 1, base - 0.1, base + 0.9))  # up trend
        base += 0.9
    # 9 bars of pullback (decline) → 9-bar lookback close is ABOVE current.
    for _ in range(9):
        rows.append((base, base + 0.1, base - 1, base - 0.9))
        base -= 0.9
    # Forming bar — open below recent close, above older close.
    rows.append((base + 0.05, base + 0.1, base, base + 0.05))
    series = candles_from_ohlc(rows)
    assert patterns.is_uptrend_with_pullback(
        series,
        uptrend_lookback=30,
        pullback_lookback=9,
    )


def test_smash_day_buy_setup_and_confirmation():
    rows = [
        (100, 101, 99.5, 100.5),  # ref bar 1 (low 99.5)
        (100, 100.5, 99.2, 100.0),  # ref bar 2 (low 99.2)
        # Smash bar: closes BELOW prior 1-bar low (99.2), not outside.
        (99.0, 99.4, 98.5, 98.7),
    ]
    series = candles_from_ohlc(rows)
    assert patterns.is_smash_day_buy_setup(series, lookback=1)

    # Confirmation: next bar closes ABOVE smash high (99.4)
    series_with_conf = candles_from_ohlc([*rows, (99.0, 100.0, 99.0, 99.5)])
    assert patterns.smash_day_buy_confirmed(series_with_conf)


def test_hidden_smash_buy_bar_lower_quartile():
    rows = [
        (100, 101, 99, 99.5),  # prev close 99.5
        # higher close vs prev (100.0 > 99.5) BUT close in lower quartile
        (99.0, 105.0, 99.0, 100.0),  # range=6.0; close pos = (100-99)/6 = 16.7%
    ]
    series = candles_from_ohlc(rows)
    assert patterns.is_hidden_smash_buy_bar(series)


def test_hidden_smash_sell_bar_upper_quartile():
    rows = [
        (100, 101, 99, 100.5),
        (101, 101.0, 95.0, 100.0),  # close=100, range=6, pos=(100-95)/6=83.3%
    ]
    series = candles_from_ohlc(rows)
    assert patterns.is_hidden_smash_sell_bar(series)


def test_scan_smash_days_finds_confirmed_setups():
    # Construct: 5 sideways bars, 1 smash, 1 confirmation.
    rows: list[tuple[float, float, float, float]] = [
        (100, 100.5, 99.5, 100.0),
        (100, 100.5, 99.5, 100.0),
        (100, 100.5, 99.5, 100.0),
        (100, 100.5, 99.5, 100.0),
        (100, 100.5, 99.5, 100.0),
        # Smash buy bar: closes below prior low (99.5).
        (99.0, 99.4, 98.5, 98.8),
        # Confirmation: closes above smash high (99.4).
        (98.5, 100.0, 98.5, 99.8),
    ]
    setups = patterns.scan_smash_days(
        candles_from_ohlc(rows),
        symbol="X",
        timeframe="D1",
        lookback=1,
    )
    assert len(setups) == 1
    s = setups[0]
    assert s.direction == "BUY"
    assert s.pattern == "smash_day"
    assert s.range_basis is not None and s.range_basis > 0
