# lwms MQL5 — Larry Williams Market Secrets

MQL5 sources for the Larry Williams indicator + Expert Advisor port.
The trading logic mirrors `src/lwms/lw/` exactly so live MT5 runs and
Python backtests stay aligned.

## File layout

```
mql5/
|-- Include/
|   `-- LWCommon.mqh                     shared helpers (enums, structs, detectors,
|                                         filling-mode, sizing, TDW, ATR, etc.)
|-- Indicators/
|   |-- LWMarketStructure.mq5            Part 1  -- 3-tier swing detector
|   |-- LWSmashDay.mq5                   Part 11 -- Smash Day arrows
|   `-- LWHiddenSmashDay.mq5             Part 14 -- Hidden Smash Day arrows
`-- Experts/
    |-- LWNonRandomTester.mq5            Part 3  -- 8-case non-random study
    |-- LWMarketStructureEA.mq5          Part 2  -- swing-confluence EA
    |-- LWShortTermSwingEA.mq5           Part 4  -- short-term swing EA
    |-- LWVolatilityBreakoutEA.mq5       Parts 5+6 -- range / swing breakout
    |-- LWPatternsEA.mq5                 Part 9  -- six "Patterns to Profit"
    |-- LWSmashDayEA.mq5                 Part 12 -- Smash Day with context
    `-- LWHiddenSmashDayEA.mq5           Part 15 -- Hidden Smash Day with context
```

The three EAs that consume an indicator (`LWMarketStructureEA`,
`LWSmashDayEA`, `LWHiddenSmashDayEA`) embed the compiled `.ex5` via the
`#resource "\\Indicators\\lwms\\<name>.ex5"` directive and load it
through `iCustom`.

## Install

Drop the MT5 `MQL5` data folder open dialog (File -> Open Data Folder)
and copy:

```
mql5/Include/LWCommon.mqh           ->  MQL5/Include/lwms/LWCommon.mqh
                                    ->  MQL5/Include/LWCommon.mqh
mql5/Indicators/*.mq5               ->  MQL5/Indicators/lwms/
mql5/Experts/*.mq5                  ->  MQL5/Experts/lwms/
```

Both copies of `LWCommon.mqh` are needed because the EAs `#include
<LWCommon.mqh>` (root) while keeping a clean per-project source folder.

PowerShell helper (run from the project root):

```powershell
$mt5 = "$env:APPDATA\MetaQuotes\Terminal\<TERMINAL_HASH>\MQL5"
$src = "D:\CODING\Trading\mt5-mcp\lwms\mql5"
New-Item -ItemType Directory -Path "$mt5\Include\lwms"   -Force | Out-Null
New-Item -ItemType Directory -Path "$mt5\Indicators\lwms" -Force | Out-Null
New-Item -ItemType Directory -Path "$mt5\Experts\lwms"   -Force | Out-Null
Copy-Item "$src\Include\LWCommon.mqh"  "$mt5\Include\lwms\" -Force
Copy-Item "$src\Include\LWCommon.mqh"  "$mt5\Include\"      -Force
Copy-Item "$src\Indicators\*.mq5"      "$mt5\Indicators\lwms\" -Force
Copy-Item "$src\Experts\*.mq5"         "$mt5\Experts\lwms\"    -Force
```

Replace `<TERMINAL_HASH>` with your terminal's data folder name (the
long hex string under `%APPDATA%\MetaQuotes\Terminal\`).

## Compile

Compile order matters because the three context EAs embed compiled
indicators as resources:

1. `Indicators/lwms/LWMarketStructure.mq5`
2. `Indicators/lwms/LWSmashDay.mq5`
3. `Indicators/lwms/LWHiddenSmashDay.mq5`
4. Everything in `Experts/lwms/`

PowerShell one-liner (uses MetaEditor's CLI):

```powershell
$me  = "C:\Program Files\MetaTrader\metaeditor64.exe"
$mt5 = "$env:APPDATA\MetaQuotes\Terminal\<TERMINAL_HASH>\MQL5"
$order = @(
  "$mt5\Indicators\lwms\LWMarketStructure.mq5",
  "$mt5\Indicators\lwms\LWSmashDay.mq5",
  "$mt5\Indicators\lwms\LWHiddenSmashDay.mq5",
  "$mt5\Experts\lwms\LWNonRandomTester.mq5",
  "$mt5\Experts\lwms\LWShortTermSwingEA.mq5",
  "$mt5\Experts\lwms\LWMarketStructureEA.mq5",
  "$mt5\Experts\lwms\LWVolatilityBreakoutEA.mq5",
  "$mt5\Experts\lwms\LWPatternsEA.mq5",
  "$mt5\Experts\lwms\LWSmashDayEA.mq5",
  "$mt5\Experts\lwms\LWHiddenSmashDayEA.mq5"
)
foreach ($f in $order) {
  $log = [System.IO.Path]::ChangeExtension($f, ".log")
  Start-Process -FilePath $me -ArgumentList "/compile:`"$f`"","/log:`"$log`"" -Wait -WindowStyle Hidden | Out-Null
  $tail = (Get-Content -LiteralPath $log -Raw -Encoding Unicode) -split "`n" | Select-Object -Last 1
  Write-Host "$(Split-Path $f -Leaf): $tail"
}
```

All files in this repo compile to **0 errors, 0 warnings** on
MetaEditor 5 (`metaeditor64.exe`).

## EA reference

### LWMarketStructure (indicator, Part 1)

3-tier swing detector. Six buffers exposed in this order:

| idx | label              | meaning                          |
|----:|--------------------|----------------------------------|
| 0   | ShortTermLows      | Williams 3-bar swing low         |
| 1   | ShortTermHighs     | mirror                           |
| 2   | IntermediateLows   | promoted from short-term lows    |
| 3   | IntermediateHighs  | promoted from short-term highs   |
| 4   | LongTermLows       | promoted from intermediate lows  |
| 5   | LongTermHighs      | promoted from intermediate highs |

Empty cells carry `EMPTY_VALUE`. Symbol on the chart is on a price
overlay; arrows are Wingdings 161 (rings) for short/intermediate and
233/234 (arrows) for long-term.

### LWSmashDay (indicator, Part 11)

Two buffers (BuySmash / SellSmash). Smash bar = bar at index 1 whose
close is below the prior N lows (buy) or above the prior N highs
(sell), is **not** an outside bar, and is followed by a confirmation
close past the smash bar's opposite extreme. Inputs:

| input | default | meaning |
|---|---|---|
| `InpBuyLookbackBars`  | 1 | prior lows the smash close must clear |
| `InpSellLookbackBars` | 1 | prior highs the smash close must clear |

### LWHiddenSmashDay (indicator, Part 14)

Two buffers. Hidden Smash bar = same-direction close vs prior bar but
close in the wrong quartile of its own range, confirmed on next bar
break of opposite extreme. Inputs:

| input | default | meaning |
|---|---|---|
| `InpQuartilePct` | 25.0 | close-position threshold (% of range) |
| `InpRequireCloseVsOpen` | false | strict: also require contrarian open/close |
| `InpValidationMode` | HIDDEN_SMASH_CONFIRMED | bar-only or confirmation-required |

### LWNonRandomTester (EA, Part 3)

One-bar BUY at every trigger. Selectable test mode prints aggregate
behaviour to the journal; useful as a Strategy Tester baseline.

### LWMarketStructureEA (EA, Part 2)

Reads `LWMarketStructure.ex5` buffers; trades on confluence between a
short-term swing and an intermediate swing at the same bar. Configurable
SL placement (short-term or intermediate extreme), min/max stop
distance, R:R target, sizing model.

### LWShortTermSwingEA (EA, Part 4)

Standalone (no indicator dependency) Williams 3-bar swing trader.
Five exit modes: hold-one-bar, RR 1:1 / 1:1.5 / 1:2 / 1:3.

### LWVolatilityBreakoutEA (EA, Parts 5 + 6)

Daily range projection with cross-over / cross-under M1 trigger.
`InpVolatilityModel` switches between Parts 5 and 6 range models.

### LWPatternsEA (EA, Part 9)

Six selectable Williams patterns:
- baseline buy-open
- N consecutive bearish
- uptrend with pullback (`open[0]>close[N]` AND `open[0]<close[M]`)
- outside-day-down close
- third bullish day fade
- N consecutive bullish buy

All but baseline arm a Part-5 volatility breakout entry on the day
following the pattern.

### LWSmashDayEA (EA, Part 12)

Reads `LWSmashDay.ex5` buffers + setup-validity countdown + optional
TDW filter. `InpSetupValidityBars` (default 3) drops setups not filled
within N bars.

### LWHiddenSmashDayEA (EA, Part 15)

Reads `LWHiddenSmashDay.ex5` buffers + ATR or structure stop +
optional TDW filter. ATR mode uses `InpAtrPeriod` (14) and
`InpAtrMult` (2.0).

## Magic numbers

Each EA uses its own default magic to avoid cross-strategy confusion:

| EA | default magic |
|---|---:|
| LWMarketStructureEA  | 254700920001 |
| LWShortTermSwingEA   | 254700930001 |
| LWNonRandomTester    | 254700910001 |
| LWVolatilityBreakoutEA | 254700950001 |
| LWPatternsEA         | 254700960001 |
| LWSmashDayEA         | 254700970001 |
| LWHiddenSmashDayEA   | 254700980001 |

Override per chart if you run two instances of the same EA on different
symbols.

## Safety

These are the **trading EAs themselves**; they are independent of the
MCP server's `MT5_DRY_RUN` / `CONFIRM_LIVE` guards. Run them on a demo
account first. The EAs respect:

- `SymbolInfoInteger(SYMBOL_FILLING_MODE)` for filling-mode detection
  (InstaForex demo defaults to RETURN; auto-resolves IOC / FOK when
  available).
- `SYMBOL_VOLUME_MIN` / `_STEP` / `_MAX` via `LW_NormalizeVolume`.
- Broker `STOPS_LEVEL` is **not** auto-padded — set
  `InpMinStopPoints` defensively when the broker is restrictive.
