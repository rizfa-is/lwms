from __future__ import annotations

from lwms.lw import nonrandom

from ._lw_helpers import alternating_series, linear_series


def test_open_to_close_bias_on_uptrend():
    series = linear_series(50)
    res = nonrandom.run_test(series, "open_to_close_bias")
    # Every triggered bar's "next bar" closes above its open by construction.
    assert res.events == len(series) - 1
    assert res.bullish_next == res.events
    assert res.bearish_next == 0
    assert res.win_rate == 1.0
    assert res.avg_pnl > 0


def test_after_one_down_on_alternating_series():
    # Alternating: bar 0 up, bar 1 down, bar 2 up, ...
    # After every "down" bar, the next bar is "up".
    series = alternating_series(40)
    res = nonrandom.run_test(series, "after_one_down")
    assert res.events > 0
    assert res.bullish_next == res.events  # always followed by up bar
    assert res.bearish_next == 0


def test_run_all_tests_returns_eight_results():
    series = linear_series(60)
    results = nonrandom.run_all_tests(series)
    assert len(results) == len(nonrandom.ALL_MODES)
    assert {r.mode for r in results} == set(nonrandom.ALL_MODES)


def test_run_test_unknown_mode_raises():
    series = linear_series(10)
    try:
        nonrandom.run_test(series, "bogus")  # type: ignore[arg-type]
    except ValueError:
        return
    raise AssertionError("expected ValueError")
