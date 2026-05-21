//+------------------------------------------------------------------+
//|                                       LWPatternsEA.mq5           |
//|                                                       lwms       |
//|     Larry Williams "Patterns to Profit" — Part 9 (article 21063)|
//+------------------------------------------------------------------+
//| Six selectable patterns from Williams' book. All but the         |
//| baseline use a Part-5 volatility-breakout entry projection on    |
//| the day after the pattern fires.                                  |
//|                                                                  |
//|   1. baseline_buy_open      — buy every new daily open           |
//|   2. consecutive_bearish    — buy after N consecutive down bars  |
//|   3. uptrend_with_pullback  — open[0] > close[N], open[0] < close[M] |
//|   4. outside_day_down_close — outside bar, bearish, close<prev.low |
//|   5. third_bullish_fade     — short after N consecutive up bars  |
//|   6. consecutive_bullish_buy- buy after N consecutive up bars    |
//+------------------------------------------------------------------+
#property copyright "lwms — Larry Williams port"
#property link      "https://github.com/rizfa-is/lwms"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <LWCommon.mqh>

enum ENUM_LW_PATTERN_MODE
{
   LW_PAT_BASELINE_BUY_OPEN,
   LW_PAT_CONSECUTIVE_BEARISH,
   LW_PAT_UPTREND_WITH_PULLBACK,
   LW_PAT_OUTSIDE_DAY_DOWN,
   LW_PAT_THIRD_BULLISH_FADE,
   LW_PAT_CONSECUTIVE_BULLISH_BUY
};

input group "Information"
input ulong                 InpMagicNumber          = 254700960001;
input ENUM_TIMEFRAMES       InpDayTimeframe         = PERIOD_D1;
input ENUM_TIMEFRAMES       InpTriggerTimeframe     = PERIOD_M1;

input group "Pattern selection"
input ENUM_LW_PATTERN_MODE  InpPatternMode          = LW_PAT_CONSECUTIVE_BEARISH;
input int                   InpRequiredConsecutive  = 3;
input int                   InpUptrendLookback      = 30;
input int                   InpPullbackLookback     = 9;

input group "Volatility entry projection"
input double                InpBuyMult              = LW_DEFAULT_BUY_MULT;
input double                InpSellMult             = LW_DEFAULT_SELL_MULT;
input double                InpStopMult             = LW_DEFAULT_STOP_MULT;
input double                InpRiskRewardRatio      = LW_DEFAULT_RR;

input group "Sizing"
input ENUM_LW_SIZING_MODEL  InpSizingModel          = LW_SIZE_RISK_PCT;
input double                InpRiskPerTradePct      = LW_DEFAULT_RISK_PCT;
input double                InpFixedLot             = 0.10;
input double                InpMaxLotSize           = 1.00;

CTrade   g_trade;
datetime g_lastDay = 0;
double   g_today_open = 0;
double   g_range = 0;
double   g_buy_level = 0;
double   g_sell_level = 0;
bool     g_armed_buy = false;
bool     g_armed_sell = false;
double   g_prev_close = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFilling(LW_DetectFillingMode(_Symbol));
   g_trade.SetDeviationInPoints(LW_DEFAULT_DEVIATION);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { }

//+------------------------------------------------------------------+
//| Pattern detectors (evaluated on a closed bar at index 1).         |
//+------------------------------------------------------------------+
bool ConsecutiveBearish() { return LW_IsConsecutiveBarCloseState(_Symbol, InpDayTimeframe, InpRequiredConsecutive, LW_BAR_DOWN); }
bool ConsecutiveBullish() { return LW_IsConsecutiveBarCloseState(_Symbol, InpDayTimeframe, InpRequiredConsecutive, LW_BAR_UP); }

bool UptrendWithPullback()
{
   if(InpUptrendLookback <= InpPullbackLookback) return false;
   const double cur_open  = iOpen (_Symbol, InpDayTimeframe, 0);
   const double far_close = iClose(_Symbol, InpDayTimeframe, InpUptrendLookback);
   const double near_close= iClose(_Symbol, InpDayTimeframe, InpPullbackLookback);
   if(cur_open == 0.0 || far_close == 0.0 || near_close == 0.0) return false;
   return (cur_open > far_close) && (cur_open < near_close);
}

bool OutsideDayDownClose()
{
   const double prev_high = iHigh (_Symbol, InpDayTimeframe, 2);
   const double prev_low  = iLow  (_Symbol, InpDayTimeframe, 2);
   const double cur_high  = iHigh (_Symbol, InpDayTimeframe, 1);
   const double cur_low   = iLow  (_Symbol, InpDayTimeframe, 1);
   const double cur_open  = iOpen (_Symbol, InpDayTimeframe, 1);
   const double cur_close = iClose(_Symbol, InpDayTimeframe, 1);
   if(prev_high == 0.0 || prev_low == 0.0 || cur_high == 0.0) return false;
   if(!LW_IsOutsideBar(prev_high, prev_low, cur_high, cur_low)) return false;
   if(cur_close >= prev_low) return false;
   if(cur_close >= cur_open) return false;
   return true;
}

//+------------------------------------------------------------------+
double ComputeVolume(const ENUM_ORDER_TYPE order_type,
                     const double entry, const double sl)
{
   if(InpSizingModel == LW_SIZE_MANUAL)
      return MathMin(InpFixedLot, InpMaxLotSize);
   const double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double v;
   if(InpSizingModel == LW_SIZE_RISK_PCT)
      v = LW_SizeBrokerAware(_Symbol, order_type, entry, sl, balance, InpRiskPerTradePct);
   else
      v = LW_SizeLegacy(_Symbol, balance, InpRiskPerTradePct, MathAbs(entry - sl));
   v = MathMin(v, InpMaxLotSize);
   return LW_NormalizeVolume(_Symbol, v);
}

bool TryOpen(const ENUM_LW_DIRECTION dir, const double entry, const double sl)
{
   if(LW_HasOpenPositionByMagic(InpMagicNumber)) return false;
   const double sl_distance = MathAbs(entry - sl);
   if(sl_distance <= 0.0) return false;
   const double tp = (dir == LW_DIR_BUY)
      ? entry + sl_distance * InpRiskRewardRatio
      : entry - sl_distance * InpRiskRewardRatio;
   const ENUM_ORDER_TYPE ot = (dir == LW_DIR_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   const double vol = ComputeVolume(ot, entry, sl);
   if(vol <= 0.0) return false;
   if(dir == LW_DIR_BUY) return g_trade.Buy (vol, _Symbol, entry, sl, tp, "LW patterns");
                          return g_trade.Sell(vol, _Symbol, entry, sl, tp, "LW patterns");
}

//+------------------------------------------------------------------+
void RearmDailyState()
{
   g_armed_buy = false;
   g_armed_sell = false;
   g_today_open = iOpen(_Symbol, InpDayTimeframe, 0);
   g_range = LW_PreviousRange(_Symbol, InpDayTimeframe);
   if(g_today_open == 0.0 || g_range <= 0.0) return;

   g_buy_level  = g_today_open + g_range * InpBuyMult;
   g_sell_level = g_today_open - g_range * InpSellMult;
   g_prev_close = iClose(_Symbol, InpTriggerTimeframe, 1);

   switch(InpPatternMode)
   {
      case LW_PAT_BASELINE_BUY_OPEN:
         // Immediate market entry on every new daily bar at the day's open.
         {
            const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            const double sl  = ask - g_range * InpStopMult;
            TryOpen(LW_DIR_BUY, ask, sl);
         }
         break;
      case LW_PAT_CONSECUTIVE_BEARISH:        g_armed_buy  = ConsecutiveBearish();   break;
      case LW_PAT_UPTREND_WITH_PULLBACK:      g_armed_buy  = UptrendWithPullback();  break;
      case LW_PAT_OUTSIDE_DAY_DOWN:           g_armed_buy  = OutsideDayDownClose();  break;
      case LW_PAT_THIRD_BULLISH_FADE:         g_armed_sell = ConsecutiveBullish();   break;
      case LW_PAT_CONSECUTIVE_BULLISH_BUY:    g_armed_buy  = ConsecutiveBullish();   break;
   }
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(LW_IsNewBar(_Symbol, InpDayTimeframe, g_lastDay))
      RearmDailyState();

   if(!g_armed_buy && !g_armed_sell) return;
   if(g_range <= 0.0) return;

   const double cur_close = iClose(_Symbol, InpTriggerTimeframe, 0);
   if(cur_close == 0.0) { g_prev_close = cur_close; return; }

   if(g_armed_buy && g_prev_close <= g_buy_level && cur_close > g_buy_level)
   {
      const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      const double sl  = ask - g_range * InpStopMult;
      if(TryOpen(LW_DIR_BUY, ask, sl)) g_armed_buy = false;
   }
   else if(g_armed_sell && g_prev_close >= g_sell_level && cur_close < g_sell_level)
   {
      const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      const double sl  = bid + g_range * InpStopMult;
      if(TryOpen(LW_DIR_SELL, bid, sl)) g_armed_sell = false;
   }
   g_prev_close = cur_close;
}
//+------------------------------------------------------------------+
