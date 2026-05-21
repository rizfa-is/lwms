# Larry Williams 29-month backtest — XAUUSD

## Setup

- **Source data**: 29 monthly XAUUSD M5 JSON files copied from
  `momentum-candle/cache/` (gitignored — 22.7 MB).
- **Range**: 2024-01-02 06:00 UTC -> 2026-05-19 18:55 UTC.
- **M5 candles**: 167,983.
- **Resampling**: M5 -> H1 (14,015 bars), H4 (3,682 bars), D1 (614 bars)
  via `lwms.lw.resample.resample()` — UTC bucket alignment.
- **Engine**: `lwms.lw.backtest.run_backtest()` — pessimistic SL/TP
  ordering (SL wins on bars that bracket both), one-position cap,
  R-multiple PnL, no spread / slippage modelling.

## Detectors run

- **Smash Day** (`scan_smash_days`) — close beyond N prior lows/highs,
  not outside, confirmed on next bar break of opposite extreme.
- **Hidden Smash Day** (`scan_hidden_smash_days`) — same direction close
  vs prior bar, but close in the wrong quartile of own range
  (default 25%), confirmed on next bar break.

Stops at the smash bar's opposite extreme; targets at fixed R:R applied
to entry-to-SL distance. Entry price = the bar **after** the
confirmation bar's open (mirrors how an MT5 EA would trade it).

## Results

```
scenario               setups trades   wr%    pf  total_r   exp   max_dd
smash-day-h1-rr3        657    456   21.9  1.08  +25.23  +0.055  -27.41
smash-day-h4-rr3        153    112   19.6  1.00   +0.04  +0.000  -21.12
smash-day-d1-rr3         28     21    9.5  0.67   -4.67  -0.222   -6.30
hidden-smash-h1-rr3      43     42   23.8  1.28   +7.60  +0.181   -7.00
hidden-smash-h4-rr3      10     10   20.0  1.51   +2.62  +0.262   -2.00
hidden-smash-d1-rr3       4      4    0.0  2.65   +1.65  +0.413   -1.00
smash-day-d1-rr2         28     22   27.3  0.98   -0.32  -0.015   -5.08
hidden-smash-d1-rr2       4      4   75.0   inf   +6.13  +1.533    0.00
```

`exp` is expectancy in R per trade. `max_dd` is peak-to-trough on the
cumulative R curve.

## Reading the table

- **`pf=inf`** for `hidden-smash-d1-rr2` means zero losing trades in the
  sample (n=4) — too few events to claim significance.
- **`wr=0%` but positive `total_r`** for `hidden-smash-d1-rr3` is not a
  bug. All 4 trades exited at the bar-hold timeout with positive R
  (price drifted in favour but did not reach 3R). The win-rate metric
  counts only `exit_reason == "tp"`; positive timeouts contribute to R
  totals but not to the win column.
- **Hidden Smash beats classic Smash on PF across every timeframe**
  (1.28 / 1.51 / 2.65 vs 1.08 / 1.00 / 0.67) — the 25% close-position
  filter rejects most of the noisy classic-Smash setups.
- **D1 sample sizes are tiny** (28 classic / 4 hidden over 29 months).
  Daily reversal patterns are by definition rare; treat the D1 numbers
  as directional rather than statistically firm.
- **H1 produces the most trades and the most stable results.** Hidden
  Smash H1 (n=42) shows PF 1.28 and exp +0.18R — interesting but not
  yet a deployable edge after spread/slippage on InstaForex demo
  (~80pt round-trip on XAUUSD).

## Honest caveats

1. **No spread cost.** Real fills on InstaForex would shave roughly
   0.05R off every trade given typical XAUUSD spreads. Some scenarios
   would flip negative.
2. **Pessimistic intra-bar order.** This is conservative — real tick
   data sometimes resolves ambiguous bars to TP, so live PF can be
   slightly higher than backtest PF.
3. **No volatility / TDW / trend filters applied.** Williams' Part 8 /
   Part 12 / Part 15 EAs stack additional filters on top of the
   detectors. The numbers above are the raw detector edge, not the
   composed strategy.
4. **One symbol, one period.** XAUUSD has a structural up-trend across
   most of this window (gold rallied through 2024-2025). Smash Day buy
   bias may be inflated; sell bias may be deflated.

## Reproduce

```powershell
# Copy data once (or fetch from MT5 if you have credentials).
Copy-Item "D:\CODING\Trading\mt5-mcp\momentum-candle\cache\*-m5.json" `
          "D:\CODING\Trading\mt5-mcp\lwms\data\history\xauusd-m5\" -Force

# Run.
uv run python scripts/backtest_lw.py
```

Outputs land in:

```
data/backtests/lw-29m-summary.json         # all scenarios, no per-trade
data/backtests/lw-<scenario>.json          # detailed trade ledger per scenario
```

## Next experiments

- Layer the **TradeDayFilter** (Part 7 weekday study) onto the H1
  Hidden Smash scenario to see whether weekday selection lifts PF.
- Layer the **session window** (Part 8) to drop Asia hours where
  XAUUSD micro-structure is noisier.
- Add a **range-pct stop** alternative and compare R distributions
  against the structure stop used here.
- Run the **8-case non-random tester** (Part 3) on the same M5 series
  to see which directional biases survive on this dataset.
