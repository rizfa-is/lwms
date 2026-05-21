from __future__ import annotations

import pytest

from lwms.lw import risk

from ._lw_helpers import candles_from_ohlc


def test_stop_loss_models_buy():
    assert risk.stop_loss_at_structure("BUY", 99.5) == 99.5
    assert risk.stop_loss_by_range_pct("BUY", entry=100.0, range_basis=10.0, stop_mult=0.5) == 95.0
    assert risk.stop_loss_by_atr("BUY", entry=100.0, atr=2.0, atr_mult=2.0) == 96.0


def test_stop_loss_models_sell_mirror():
    assert (
        risk.stop_loss_by_range_pct("SELL", entry=100.0, range_basis=10.0, stop_mult=0.5) == 105.0
    )
    assert risk.stop_loss_by_atr("SELL", entry=100.0, atr=2.0, atr_mult=2.0) == 104.0


def test_take_profit_by_rr():
    # entry 100, sl 95 → distance 5; rr=3 → tp = 100 + 15 = 115
    assert risk.take_profit_by_rr("BUY", 100.0, 95.0, 3.0) == 115.0
    # SELL: entry 100, sl 105 → tp = 100 - 15 = 85
    assert risk.take_profit_by_rr("SELL", 100.0, 105.0, 3.0) == 85.0


def test_build_risk_plan_validates_sl_side():
    with pytest.raises(ValueError):
        risk.build_risk_plan(direction="BUY", entry=100.0, sl=101.0)
    with pytest.raises(ValueError):
        risk.build_risk_plan(direction="SELL", entry=100.0, sl=99.0)


def test_size_legacy_basic():
    # balance 10000, risk 1% = 100; contract=100, sl_distance=2 → 100/(100*2) = 0.5
    v = risk.size_legacy(balance=10000.0, risk_pct=1.0, contract_size=100.0, sl_distance=2.0)
    # constrained by step 0.01 → 0.50
    assert v == 0.50


def test_size_broker_uses_loss_per_lot():
    # risk 1% of 10000 = 100. loss_per_lot = 200 → 100/200 = 0.5 lots
    v = risk.size_broker(balance=10000.0, risk_pct=1.0, loss_per_lot=200.0)
    assert v == 0.50


def test_size_returns_zero_on_bad_input():
    assert risk.size_legacy(balance=0.0, risk_pct=1.0, contract_size=100.0, sl_distance=1.0) == 0.0
    assert risk.size_broker(balance=10000.0, risk_pct=1.0, loss_per_lot=0.0) == 0.0


def test_normalize_volume_clamps_and_steps():
    c = risk.VolumeConstraints(volume_min=0.01, volume_step=0.01, volume_max=2.0)
    assert risk.normalize_volume(0.027, c) == 0.02
    assert risk.normalize_volume(5.0, c) == 2.0
    assert risk.normalize_volume(0.001, c) == 0.01


def test_wilder_atr_returns_value_when_enough_data():
    # 30 bars of constant range 1.0; ATR should be 1.0 within a tiny tolerance.
    rows = [(100.0, 101.0, 99.0, 100.5) for _ in range(30)]
    series = candles_from_ohlc(rows)
    highs = [c["high"] for c in series]
    lows = [c["low"] for c in series]
    closes = [c["close"] for c in series]
    atr = risk.wilder_atr(highs, lows, closes, period=14)
    assert atr is not None
    assert abs(atr - 2.0) < 1e-6  # range = high-low = 2.0 here


def test_wilder_atr_insufficient_data():
    assert risk.wilder_atr([1, 2], [0, 1], [1, 1], period=14) is None
