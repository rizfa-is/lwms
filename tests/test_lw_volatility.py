from __future__ import annotations

import pytest

from lwms.lw import volatility

from ._lw_helpers import candles_from_ohlc


def test_previous_range_basic():
    series = candles_from_ohlc([(100, 110, 95, 105), (105, 115, 100, 110)])
    # previous bar (-2) range = 110 - 95 = 15
    assert volatility.previous_range(series) == 15.0


def test_swing_dominant_range_picks_max():
    # candles[-5..-1] required → 5 bars
    rows = [
        (90, 100, 80, 95),  # bar4 (3 days ago)  high=100 low=80
        (95, 105, 90, 100),  # bar3
        (100, 110, 95, 105),  # bar2 (1 day ago) high=110 low=95
        (105, 115, 100, 110),  # bar1 (yesterday) high=115 low=100
        (110, 116, 109, 112),  # bar0 forming
    ]
    series = candles_from_ohlc(rows)
    # swingA = |bar4.high - bar1.low| = |100 - 100| = 0
    # swingB = |bar2.high - bar4.low| = |110 - 80| = 30
    assert volatility.swing_dominant_range(series) == 30.0


def test_project_breakout_levels_previous_range():
    series = candles_from_ohlc(
        [
            (100, 110, 90, 105),  # prev: range = 20
            (105, 105, 105, 105),  # forming: open = 105
        ]
    )
    levels = volatility.project_breakout_levels(
        series,
        model="previous_range",
        buy_mult=0.5,
        sell_mult=0.5,
        stop_mult=0.5,
    )
    # range=20, 0.5x = 10
    assert levels.today_open == 105
    assert levels.range_basis == 20
    assert levels.buy_entry == 115  # 105 + 10
    assert levels.sell_entry == 95  # 105 - 10
    assert levels.long_stop == 105  # 115 - 10
    assert levels.short_stop == 105  # 95 + 10


def test_project_breakout_levels_unknown_model_raises():
    series = candles_from_ohlc([(1, 2, 0, 1), (1, 2, 0, 1)])
    with pytest.raises(ValueError):
        volatility.project_breakout_levels(series, model="bogus")  # type: ignore[arg-type]
