//+------------------------------------------------------------------+
//|                                                    LWCommon.mqh  |
//|                                                       lwms       |
//|                              Larry Williams Market Secrets port  |
//+------------------------------------------------------------------+
//| Shared helpers, enums, and structs used by the LW indicators and |
//| Expert Advisors in this project. Concepts ported from the 15-part|
//| MQL5 article series by Chacha Ian Maroa (articles 20510-21393).  |
//|                                                                  |
//| Drop this file into <MT5 data folder>/MQL5/Include/.             |
//+------------------------------------------------------------------+
#property strict

#ifndef LW_COMMON_MQH
#define LW_COMMON_MQH

//+------------------------------------------------------------------+
//| Direction & state enums                                           |
//+------------------------------------------------------------------+
enum ENUM_LW_DIRECTION
{
   LW_DIR_NONE = 0,
   LW_DIR_BUY  = 1,
   LW_DIR_SELL = -1
};

enum ENUM_LW_BAR_STATE
{
   LW_BAR_UP,
   LW_BAR_DOWN
};

enum ENUM_LW_TRADE_DIRECTION
{
   LW_TRADE_LONG_ONLY,
   LW_TRADE_SHORT_ONLY,
   LW_TRADE_BOTH
};

//+------------------------------------------------------------------+
//| Stop-loss / take-profit / sizing models                          |
//+------------------------------------------------------------------+
enum ENUM_LW_SL_MODEL
{
   LW_SL_STRUCTURE,        // SL at swing / smash bar extreme
   LW_SL_RANGE_PCT,        // SL = entry +/- range_basis * stop_mult
   LW_SL_ATR               // SL = entry +/- ATR(period) * mult
};

enum ENUM_LW_TP_MODEL
{
   LW_TP_FIXED_RR,         // TP at fixed risk:reward applied to SL distance
   LW_TP_FIRST_PROFIT_OPEN,// close on first new bar open showing profit
   LW_TP_AFTER_N_BARS      // close after N bars
};

enum ENUM_LW_SIZING_MODEL
{
   LW_SIZE_MANUAL,         // fixed lot size
   LW_SIZE_RISK_PCT,       // risk_pct of balance / loss-per-lot (broker-aware)
   LW_SIZE_LEGACY          // risk_pct/100 * balance / (contract * sl_distance)
};

enum ENUM_LW_VOLATILITY_MODEL
{
   LW_VOL_PREVIOUS_RANGE,  // Part 5 — yesterday's range
   LW_VOL_SWING_BASED      // Part 6 — 3-day swing dominant range
};

//+------------------------------------------------------------------+
//| Risk plan struct                                                 |
//+------------------------------------------------------------------+
struct LWRiskPlan
{
   double entry;
   double sl;
   double tp;
   double sl_distance;
   double rr;
   double volume;
};

//+------------------------------------------------------------------+
//| Reusable defaults                                                |
//+------------------------------------------------------------------+
#define LW_DEFAULT_RR              3.0
#define LW_DEFAULT_STOP_MULT       0.50
#define LW_DEFAULT_BUY_MULT        0.50
#define LW_DEFAULT_SELL_MULT       0.50
#define LW_DEFAULT_ATR_PERIOD      14
#define LW_DEFAULT_ATR_MULT        2.0
#define LW_DEFAULT_RISK_PCT        1.0
#define LW_DEFAULT_QUARTILE_PCT    25.0
#define LW_DEFAULT_SMASH_LOOKBACK  1
#define LW_DEFAULT_HOLD_BARS       30
#define LW_DEFAULT_DEVIATION       30

//+------------------------------------------------------------------+
//| New-bar detector (call once per OnTick).                          |
//+------------------------------------------------------------------+
bool LW_IsNewBar(const string symbol, const ENUM_TIMEFRAMES tf, datetime &lastTm)
{
   const datetime cur = iTime(symbol, tf, 0);
   if(cur == 0)            return false;
   if(cur == lastTm)       return false;
   lastTm = cur;
   return true;
}

//+------------------------------------------------------------------+
//| Outside / inside bar tests (forward orientation: prev = older).  |
//| When called on series-indexed arrays, pass the older bar first.  |
//+------------------------------------------------------------------+
bool LW_IsOutsideBar(const double prev_high, const double prev_low,
                     const double cur_high,  const double cur_low)
{
   return (cur_high > prev_high && cur_low < prev_low);
}

bool LW_IsInsideBar(const double prev_high, const double prev_low,
                    const double cur_high,  const double cur_low)
{
   return (cur_high < prev_high && cur_low > prev_low);
}

//+------------------------------------------------------------------+
//| Consecutive same-direction closes (article 21063 helper).        |
//| Inspects bars 1..N (closed bars) on the chart timeframe.         |
//+------------------------------------------------------------------+
bool LW_IsConsecutiveBarCloseState(const string symbol,
                                   const ENUM_TIMEFRAMES tf,
                                   const int barsToCheck,
                                   const ENUM_LW_BAR_STATE state)
{
   if(barsToCheck < 1) return false;
   for(int i = 1; i <= barsToCheck; i++)
   {
      const double op = iOpen (symbol, tf, i);
      const double cl = iClose(symbol, tf, i);
      if(op == 0.0 || cl == 0.0) return false;
      if(state == LW_BAR_UP   && cl <= op) return false;
      if(state == LW_BAR_DOWN && cl >= op) return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Article-3 short-term low / high (with outside + inside filters). |
//+------------------------------------------------------------------+
bool LW_IsShortTermLow(const string symbol, const ENUM_TIMEFRAMES tf)
{
   const double h1 = iHigh(symbol, tf, 1);
   const double l1 = iLow (symbol, tf, 1);
   const double h2 = iHigh(symbol, tf, 2);
   const double l2 = iLow (symbol, tf, 2);
   const double h3 = iHigh(symbol, tf, 3);
   const double l3 = iLow (symbol, tf, 3);
   if(h1 == 0.0 || l1 == 0.0 || h2 == 0.0 || h3 == 0.0) return false;
   if(!(l2 < l1 && l2 < l3))               return false;
   if(LW_IsOutsideBar(h3, l3, h2, l2))      return false;
   if(LW_IsInsideBar (h2, l2, h1, l1))      return false;
   return true;
}

bool LW_IsShortTermHigh(const string symbol, const ENUM_TIMEFRAMES tf)
{
   const double h1 = iHigh(symbol, tf, 1);
   const double l1 = iLow (symbol, tf, 1);
   const double h2 = iHigh(symbol, tf, 2);
   const double l2 = iLow (symbol, tf, 2);
   const double h3 = iHigh(symbol, tf, 3);
   const double l3 = iLow (symbol, tf, 3);
   if(h1 == 0.0 || l1 == 0.0 || h2 == 0.0 || h3 == 0.0) return false;
   if(!(h2 > h1 && h2 > h3))                return false;
   if(LW_IsOutsideBar(h3, l3, h2, l2))      return false;
   if(LW_IsInsideBar (h2, l2, h1, l1))      return false;
   return true;
}

//+------------------------------------------------------------------+
//| Volatility-breakout range (Parts 5 / 6).                         |
//+------------------------------------------------------------------+
double LW_PreviousRange(const string symbol, const ENUM_TIMEFRAMES tf)
{
   return iHigh(symbol, tf, 1) - iLow(symbol, tf, 1);
}

double LW_SwingDominantRange(const string symbol, const ENUM_TIMEFRAMES tf)
{
   const double swingA = MathAbs(iHigh(symbol, tf, 4) - iLow(symbol, tf, 1));
   const double swingB = MathAbs(iHigh(symbol, tf, 2) - iLow(symbol, tf, 4));
   return MathMax(swingA, swingB);
}

double LW_SelectVolatilityRange(const string symbol,
                                const ENUM_TIMEFRAMES tf,
                                const ENUM_LW_VOLATILITY_MODEL model)
{
   if(model == LW_VOL_SWING_BASED) return LW_SwingDominantRange(symbol, tf);
   return LW_PreviousRange(symbol, tf);
}

//+------------------------------------------------------------------+
//| Smash Day detectors (Parts 10-15).                                |
//| Smash bar = bar at index 1 on the chart (last fully closed bar). |
//| Confirmation evaluated on the forming bar's open.                 |
//+------------------------------------------------------------------+
bool LW_IsSmashDayBuyBar(const string symbol, const ENUM_TIMEFRAMES tf,
                         const int lookback)
{
   if(lookback < 1) return false;
   const double smash_close = iClose(symbol, tf, 1);
   const double smash_high  = iHigh (symbol, tf, 1);
   const double smash_low   = iLow  (symbol, tf, 1);
   if(smash_close == 0.0) return false;

   for(int k = 1; k <= lookback; k++)
   {
      const double prev_low = iLow(symbol, tf, 1 + k);
      if(prev_low == 0.0)            return false;
      if(smash_close >= prev_low)    return false;
   }

   const double prev_high = iHigh(symbol, tf, 2);
   const double prev_low2 = iLow (symbol, tf, 2);
   if(LW_IsOutsideBar(prev_high, prev_low2, smash_high, smash_low)) return false;
   return true;
}

bool LW_IsSmashDaySellBar(const string symbol, const ENUM_TIMEFRAMES tf,
                          const int lookback)
{
   if(lookback < 1) return false;
   const double smash_close = iClose(symbol, tf, 1);
   const double smash_high  = iHigh (symbol, tf, 1);
   const double smash_low   = iLow  (symbol, tf, 1);
   if(smash_close == 0.0) return false;

   for(int k = 1; k <= lookback; k++)
   {
      const double prev_high = iHigh(symbol, tf, 1 + k);
      if(prev_high == 0.0)             return false;
      if(smash_close <= prev_high)     return false;
   }

   const double prev_high2 = iHigh(symbol, tf, 2);
   const double prev_low2  = iLow (symbol, tf, 2);
   if(LW_IsOutsideBar(prev_high2, prev_low2, smash_high, smash_low)) return false;
   return true;
}

//+------------------------------------------------------------------+
//| Hidden Smash Day detectors (Parts 13-15).                         |
//+------------------------------------------------------------------+
double LW_ClosePositionPct(const double op, const double hi, const double lo, const double cl)
{
   const double rng = hi - lo;
   if(rng <= 0.0) return 50.0;
   return (cl - lo) / rng * 100.0;
}

bool LW_IsHiddenSmashBuyBar(const string symbol, const ENUM_TIMEFRAMES tf,
                            const double quartile_pct,
                            const bool   require_close_below_open)
{
   const double op   = iOpen (symbol, tf, 1);
   const double hi   = iHigh (symbol, tf, 1);
   const double lo   = iLow  (symbol, tf, 1);
   const double cl   = iClose(symbol, tf, 1);
   const double prev = iClose(symbol, tf, 2);
   if(cl == 0.0 || prev == 0.0) return false;
   if(cl <= prev)               return false;
   const double rng = hi - lo;
   if(rng <= 0.0)               return false;
   if(LW_ClosePositionPct(op, hi, lo, cl) > quartile_pct) return false;
   if(require_close_below_open && cl >= op)               return false;
   return true;
}

bool LW_IsHiddenSmashSellBar(const string symbol, const ENUM_TIMEFRAMES tf,
                             const double quartile_pct,
                             const bool   require_close_above_open)
{
   const double op   = iOpen (symbol, tf, 1);
   const double hi   = iHigh (symbol, tf, 1);
   const double lo   = iLow  (symbol, tf, 1);
   const double cl   = iClose(symbol, tf, 1);
   const double prev = iClose(symbol, tf, 2);
   if(cl == 0.0 || prev == 0.0) return false;
   if(cl >= prev)               return false;
   const double rng = hi - lo;
   if(rng <= 0.0)               return false;
   if(LW_ClosePositionPct(op, hi, lo, cl) < (100.0 - quartile_pct)) return false;
   if(require_close_above_open && cl <= op)                          return false;
   return true;
}

//+------------------------------------------------------------------+
//| Filling mode auto-detect (InstaForex demo compat).                |
//+------------------------------------------------------------------+
ENUM_ORDER_TYPE_FILLING LW_DetectFillingMode(const string symbol)
{
   const long flags = SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE);
   if((flags & SYMBOL_FILLING_IOC) != 0) return ORDER_FILLING_IOC;
   if((flags & SYMBOL_FILLING_FOK) != 0) return ORDER_FILLING_FOK;
   return ORDER_FILLING_RETURN;
}

//+------------------------------------------------------------------+
//| Volume normalisation against broker constraints.                 |
//+------------------------------------------------------------------+
double LW_NormalizeVolume(const string symbol, const double vol_in)
{
   const double vmin  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   const double vmax  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(vstep <= 0.0) vstep = 0.01;
   double v = MathMax(vmin, MathMin(vol_in, vmax));
   const double steps = MathFloor(v / vstep);
   return NormalizeDouble(steps * vstep, 2);
}

//+------------------------------------------------------------------+
//| Position sizing — legacy + broker-aware.                          |
//+------------------------------------------------------------------+
double LW_SizeLegacy(const string symbol,
                     const double balance,
                     const double risk_pct,
                     const double sl_distance)
{
   if(balance <= 0.0 || risk_pct <= 0.0 || sl_distance <= 0.0) return 0.0;
   const double contract = SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(contract <= 0.0) return 0.0;
   const double risk_money = (risk_pct / 100.0) * balance;
   const double raw = risk_money / (contract * sl_distance);
   return LW_NormalizeVolume(symbol, raw);
}

double LW_SizeBrokerAware(const string symbol,
                          const ENUM_ORDER_TYPE order_type,
                          const double entry,
                          const double sl,
                          const double balance,
                          const double risk_pct)
{
   if(balance <= 0.0 || risk_pct <= 0.0) return 0.0;
   double loss_per_lot = 0.0;
   if(!OrderCalcProfit(order_type, symbol, 1.0, entry, sl, loss_per_lot)) return 0.0;
   loss_per_lot = MathAbs(loss_per_lot);
   if(loss_per_lot <= 0.0) return 0.0;
   const double risk_money = (risk_pct / 100.0) * balance;
   const double raw = risk_money / loss_per_lot;
   return LW_NormalizeVolume(symbol, raw);
}

//+------------------------------------------------------------------+
//| Trade-Day-of-Week filter (Part 7). Sun=0..Sat=6 (MQL5 native).    |
//+------------------------------------------------------------------+
struct LWTradeDayFilter
{
   bool sun, mon, tue, wed, thu, fri, sat;
};

void LW_TradeDay_AllDays(LWTradeDayFilter &f)
{
   f.sun = true; f.mon = true; f.tue = true; f.wed = true;
   f.thu = true; f.fri = true; f.sat = true;
}

void LW_TradeDay_WeekdaysOnly(LWTradeDayFilter &f)
{
   f.sun = false; f.sat = false;
   f.mon = true; f.tue = true; f.wed = true; f.thu = true; f.fri = true;
}

bool LW_TradeDay_IsAllowed(const LWTradeDayFilter &f, const datetime ts)
{
   MqlDateTime dt;
   TimeToStruct(ts, dt);
   switch(dt.day_of_week)
   {
      case 0: return f.sun;
      case 1: return f.mon;
      case 2: return f.tue;
      case 3: return f.wed;
      case 4: return f.thu;
      case 5: return f.fri;
      case 6: return f.sat;
   }
   return false;
}

//+------------------------------------------------------------------+
//| RR target helper.                                                 |
//+------------------------------------------------------------------+
double LW_TpFromRR(const ENUM_LW_DIRECTION dir, const double entry,
                   const double sl, const double rr)
{
   const double sl_distance = MathAbs(entry - sl);
   if(dir == LW_DIR_BUY)  return entry + sl_distance * rr;
   return entry - sl_distance * rr;
}

//+------------------------------------------------------------------+
//| Active-position check by magic number.                            |
//+------------------------------------------------------------------+
bool LW_HasOpenPositionByMagic(const ulong magic)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) == magic)
         return true;
   }
   return false;
}

#endif // LW_COMMON_MQH
