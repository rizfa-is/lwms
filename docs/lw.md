# Larry Williams Market Secrets — Python port

This document maps the 15-part MQL5 article series by Chacha Ian Maroa
(articles 20510-21393 on mql5.com) to the Python modules under
`src/lwms/lw/`. The MQL5 originals ship indicators and Expert Advisors;
this port keeps the **analytical core** as pure-Python functions over
candle dicts so the same logic is testable without a live MT5 terminal.

## Article -> module mapping

| Part | MQL5 article | Concept | Python module |
|---|---|---|---|
| 1 | 20511 | Swing structure indicator (3 tiers) | `lw.structure.find_market_structure` |
| 2 | 20512 | Market structure trading EA | `lw.structure` + `lw.risk` + `lw.signals` |
| 3 | 20510 | Non-random behavior tester (8 cases) | `lw.nonrandom.run_all_tests` |
| 4 | 20716 | Short-term swing high/low EA | `lw.structure.is_larry_williams_short_term_low` |
| 5 | 20745 | Volatility breakout (yesterday's range) | `lw.volatility.previous_range` + `project_breakout_levels(model="previous_range")` |
| 6 | 20862 | Volatility breakout (swing-based) | `lw.volatility.swing_dominant_range` + `project_breakout_levels(model="swing_based")` |
| 7 | 20941 | Trade Day of the Week study | `lw.filters.TradeDayFilter` |
| 8 | 21003 | Volatility + structure + time composite | `lw.volatility` + `lw.structure` + `lw.filters` |
| 9 | 21063 | Patterns to Profit (six strategies) | `lw.patterns` (`is_consecutive_close_state`, `is_uptrend_with_pullback`, `is_outside_day_down_close`) |
| 10 | 21127 | Smash Day reversal automation | `lw.patterns.is_smash_day_buy_setup` / `scan_smash_days` |
| 11 | 21128 | Smash Day indicator | same detectors as Part 10 (no separate module needed) |
| 12 | 21228 | Smash Day with context filters | `lw.patterns.scan_smash_days` + `lw.filters` |
| 13 | 21391 | Hidden Smash Day reversal automation | `lw.patterns.is_hidden_smash_buy_bar` / `scan_hidden_smash_days` |
| 14 | 21392 | Hidden Smash Day indicator | same detectors as Part 13 |
| 15 | 21393 | Hidden Smash Day with market context | `lw.patterns` + `lw.filters` + `lw.risk` |

## Module layout

```
src/lwms/lw/
  __init__.py     re-exports Candle, Setup, ohlc_arrays
  bars.py         Candle dataclass + outside/inside/cross helpers
  signals.py      Setup dataclass — universal detector output shape
  structure.py    3-tier swing detector + LW short-term low/high
  patterns.py     consecutive closes, outside-day-down, pullback,
                  Smash Day, Hidden Smash Day (+ scanners)
  volatility.py   yesterday-range / swing-based projections
  filters.py      TradeDayFilter, SessionWindow, ContextFilter
  risk.py         SL models (structure / range_pct / ATR), RR TP,
                  position sizing (legacy + broker-aware), Wilder ATR
  nonrandom.py    8-case Larry Williams non-random behaviour tester
```

All modules:

- take **oldest-first** candle dict lists (the same shape returned by
  `lwms.market.get_candles_latest`)
- never import `MetaTrader5` (so unit tests run anywhere)
- return either booleans, dataclasses, or `Setup` instances
- are wired through `server.py` as MCP tools (`lw_*`)

## Bar indexing translation

The MQL5 articles use reverse-time indexing (newest=0). Python uses
forward indexing (oldest=0). The translation:

| MQL5 (reverse) | Python (forward) |
|---|---|
| `iClose(0)` (forming bar) | `candles[-1]["close"]` |
| `iClose(1)` (last closed bar) | `candles[-2]["close"]` |
| `iClose(N)` | `candles[-1 - N]["close"]` |

`bars.mql5_index(forward, total)` and `bars.from_mql5_index(reverse,
total)` round-trip between the two views when you need explicit
indices.

## Default thresholds

Mirrors the article series defaults exactly:

- `DEFAULT_SMASH_LOOKBACK = 1`
- `DEFAULT_HIDDEN_SMASH_QUARTILE_PCT = 25.0`
- `DEFAULT_CONSECUTIVE_BARS = 3`
- `DEFAULT_UPTREND_LOOKBACK = 30`, `DEFAULT_PULLBACK_LOOKBACK = 9`
- `DEFAULT_BUY_MULT = DEFAULT_SELL_MULT = DEFAULT_STOP_MULT = 0.50`
- `DEFAULT_RR = 3.0`
- `DEFAULT_ATR_PERIOD = 14`, `DEFAULT_ATR_MULT = 2.0`
- `DEFAULT_RISK_PCT = 1.0`

## MCP tools (read-only)

All registered in `lwms.server`:

| Tool | Wraps |
|---|---|
| `lw_market_structure` | `structure.find_market_structure` |
| `lw_smash_day_setups` | `patterns.scan_smash_days` |
| `lw_hidden_smash_day_setups` | `patterns.scan_hidden_smash_days` |
| `lw_volatility_breakout_levels` | `volatility.project_breakout_levels` |
| `lw_nonrandom_test` | `nonrandom.run_test` / `run_all_tests` |
| `lw_consecutive_close_check` | `patterns.is_consecutive_close_state` |

Each tool returns plain dicts (or lists of dicts) — JSON-safe through
the MCP transport.

## Composition pattern

Williams' EAs in the later articles (Parts 8, 12, 15) follow the same
recipe:

```
signal x volatility-projection x trend-filter x time-filter x risk-plan
```

The pure-Python equivalent in this package is:

```python
from lwms.lw import filters, patterns, risk, volatility

candles = market.get_candles_latest(symbol="XAUUSD", timeframe="D1", count=300)
setups = patterns.scan_hidden_smash_days(candles, symbol="XAUUSD", timeframe="D1")

ctx = filters.ContextFilter(
    tdw=filters.TradeDayFilter.weekdays_only(),
    session=None,
)

for s in setups:
    if not ctx.allows(s.trigger_time):
        continue
    smash_low = s.extras["smash_low"]
    plan = risk.build_risk_plan(
        direction=s.direction,
        entry=s.trigger_price,
        sl=risk.stop_loss_at_structure(s.direction, smash_low),
        rr=3.0,
    )
    print(plan)
```

The MCP tool layer wraps these primitives but also exposes them
individually — agents can call `lw_volatility_breakout_levels` and feed
the result into `place_market_order` directly.

## What's intentionally not ported

- **Chart appearance helpers** (`ChartSetInteger` / colours / arrows) —
  pure cosmetics from the MQL5 indicators.
- **Trade execution / position management** — already handled by
  `lwms.trade` (dry-run guarded).
- **Supertrend indicator handle** (Parts 12, 15) — Python detection
  would be a separate module; not a Larry Williams concept.
- **One-position-per-magic enforcement** — already in `lwms.trade.get_positions`.

## Verification

```powershell
uv run pytest                # 59 tests, all green
uv run ruff check .          # All checks passed
```

The 7 LW tests cover every public detector / projection / filter:

- `tests/test_lw_structure.py` — bars, structure, swing detection
- `tests/test_lw_patterns.py` — consecutive, outside-day, pullback,
  Smash, Hidden Smash, scanners
- `tests/test_lw_volatility.py` — both range models + projection
- `tests/test_lw_filters.py` — TDW, session, context bundle
- `tests/test_lw_risk.py` — SL models, TP, sizing, ATR
- `tests/test_lw_nonrandom.py` — 8-case tester
- `tests/_lw_helpers.py` — synthetic candle factory shared across tests
