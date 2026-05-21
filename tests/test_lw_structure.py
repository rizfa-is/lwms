from __future__ import annotations

from lwms.lw import structure
from lwms.lw.bars import (
    Candle,
    crossover,
    crossunder,
    is_inside_bar,
    is_outside_bar,
    mql5_index,
    ohlc_arrays,
)

from ._lw_helpers import candles_from_ohlc, make_candle


def test_candle_from_dict_roundtrip():
    d = make_candle(time=1, open=10, high=12, low=9, close=11)
    c = Candle.from_dict(d)
    assert c.open == 10
    assert c.high == 12
    assert c.range == 3
    assert c.body == 1
    assert c.is_bullish
    assert not c.is_bearish


def test_ohlc_arrays_split():
    series = candles_from_ohlc([(1, 2, 0.5, 1.5), (1.5, 2.5, 1.0, 2.0)])
    o, h, lo, cl, v = ohlc_arrays(series)
    assert o == [1.0, 1.5]
    assert h == [2.0, 2.5]
    assert lo == [0.5, 1.0]
    assert cl == [1.5, 2.0]
    assert v == [1000, 1000]


def test_outside_and_inside_bar():
    prev = make_candle(time=1, open=10, high=11, low=9, close=10.5)
    outside = make_candle(time=2, open=10, high=12, low=8, close=10)
    inside = make_candle(time=2, open=10, high=10.5, low=9.5, close=10.2)
    assert is_outside_bar(prev, outside)
    assert not is_inside_bar(prev, outside)
    assert is_inside_bar(prev, inside)
    assert not is_outside_bar(prev, inside)


def test_mql5_index_round_trip():
    assert mql5_index(0, 5) == 4
    assert mql5_index(4, 5) == 0


def test_crossover_and_crossunder():
    assert crossover(99.0, 101.0, 100.0)
    assert not crossover(101.0, 102.0, 100.0)
    assert crossunder(101.0, 99.0, 100.0)
    assert not crossunder(99.0, 98.0, 100.0)


def test_short_term_swing_low_three_bar_strict():
    candles = candles_from_ohlc(
        [
            # strictly higher low on left
            (10, 11, 9.5, 10.5),
            # candidate swing low
            (10, 11, 9.0, 10.5),
            # higher low on right
            (10, 11, 9.4, 10.5),
        ]
    )
    # MUST also pass outside / inside filters; engineered bars satisfy both.
    assert structure.is_larry_williams_short_term_low(candles)


def test_short_term_swing_low_rejects_outside_bar():
    # bar2 (the swing) is outside relative to bar3 → rejected.
    candles = candles_from_ohlc(
        [
            (10, 10.5, 9.5, 10),
            (10, 11, 9.0, 10.5),  # outside bar wrt previous
            (10, 10.5, 9.4, 10.5),
        ]
    )
    assert not structure.is_larry_williams_short_term_low(candles)


def test_find_market_structure_three_tiers():
    # Construct an explicit zig-zag with three short-tier highs whose middle
    # is highest (=> guarantees one intermediate high).
    pattern = [
        (10, 11.0, 9, 10),
        (10, 11.5, 9, 11),  # short high #1 (price 11.5)
        (11, 11.0, 8, 9),  # short low
        (9, 13.0, 9, 12),  # short high #2 (price 13.0) — middle, highest
        (12, 12.0, 7, 8),  # short low
        (8, 12.5, 8, 11),  # short high #3 (price 12.5)
        (11, 11.0, 9, 10),
    ]
    candles = candles_from_ohlc(pattern)
    ms = structure.find_market_structure(candles)
    assert len(ms.short_highs) >= 3
    # Middle short-high (price 13.0) should promote to intermediate.
    assert any(p.price == 13.0 for p in ms.intermediate_highs)
