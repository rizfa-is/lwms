from __future__ import annotations

from lwms.lw import resample

from ._lw_helpers import make_candle


def _m5_series(start_epoch: int, count: int) -> list[dict]:
    out = []
    base = 100.0
    for i in range(count):
        out.append(
            make_candle(
                time=start_epoch + i * 300,
                open=base,
                high=base + 1.0,
                low=base - 0.5,
                close=base + 0.5,
            )
        )
        base += 0.1
    return out


# An epoch that floors cleanly to both M15 (900s) and H1 (3600s) buckets.
ALIGNED_EPOCH = 1_700_006_400  # 2023-11-14 22:40 UTC -> aligned to hour


def test_resample_m5_to_m15_groups_three_bars():
    # 9 M5 bars -> 3 M15 bars
    bars = _m5_series(start_epoch=ALIGNED_EPOCH, count=9)
    h = resample.resample(bars, "M15")
    assert len(h) == 3
    # Each H1 bar's high is max of its three children, low is min.
    for i, hb in enumerate(h):
        children = bars[i * 3 : (i + 1) * 3]
        assert hb["high"] == max(c["high"] for c in children)
        assert hb["low"] == min(c["low"] for c in children)
        assert hb["open"] == children[0]["open"]
        assert hb["close"] == children[-1]["close"]
        assert hb["tick_volume"] == sum(c["tick_volume"] for c in children)


def test_resample_h1_buckets_align_to_hour():
    # 12 M5 bars covering exactly 1 hour
    bars = _m5_series(start_epoch=ALIGNED_EPOCH, count=12)
    h = resample.resample(bars, "H1")
    assert len(h) == 1
    # Bucket time should floor to the start of the hour.
    assert h[0]["time"] == (ALIGNED_EPOCH // 3600) * 3600


def test_resample_unknown_tf_raises():
    bars = _m5_series(start_epoch=1, count=3)
    try:
        resample.resample(bars, "X9")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_resample_empty_input():
    assert resample.resample([], "H1") == []
