//+------------------------------------------------------------------+
//|                                       LWVolatilityBreakoutEA.mq5 |
//|                                                       lwms       |
//|     Larry Williams volatility breakout — Parts 5 + 6 (20745/862)|
//+------------------------------------------------------------------+
//| Once per new bar (typically D1) the EA computes:                 |
//|   range_basis = previous-day range OR 3-day swing-dominant range |
//|   buy_entry   = today_open + range_basis * InpBuyMult             |
//|   sell_entry  = today_open - range_basis * InpSellMult            |
//|   long_stop   = buy_entry  - range_basis * InpStopMult            |
//|   short_stop  = sell_entry + range_basis * InpStopMult            |
//|                                                                  |
//| It then waits for an intra-day M1 close to cross above/below     |
//| these levels and opens the corresponding market position. One    |
//| trade per direction per day; reset every new daily bar.          |
//+------------------------------------------------------------------+
#property copyright "lwms — Larry Williams port"
#property link      "https://github.com/rizfa-is/lwms"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <LWCommon.mqh>

input group "Information"
input ulong                  InpMagicNumber          = 254700950001;
input ENUM_TIMEFRAMES        InpDayTimeframe         = PERIOD_D1;
input ENUM_TIMEFRAMES        InpTriggerTimeframe     = PERIOD_M1;

input group "Volatility model"
input ENUM_LW_VOLATILITY_MODEL InpVolatilityModel    = LW_VOL_PREVIOUS_RANGE;
input double                 InpBuyMult              = LW_DEFAULT_BUY_MULT;
input double                 InpSellMult             = LW_DEFAULT_SELL_MULT;
input double                 InpStopMult             = LW_DEFAULT_STOP_MULT;
input double                 InpRewardValue          = 4.0;
input ENUM_LW_TRADE_DIRECTION InpDirection           = LW_TRADE_BOTH;

input group "Sizing"
input ENUM_LW_SIZING_MODEL   InpSizingModel          = LW_SIZE_RISK_PCT;
input double                 InpRiskPerTradePct      = LW_DEFAULT_RISK_PCT;
input double                 InpFixedLot             = 0.10;
input double                 InpMaxLotSize           = 1.00;

CTrade   g_trade;
datetime g_lastDay = 0;
double   g_today_open = 0;
double   g_range = 0;
double   g_buy_entry = 0;
double   g_sell_entry = 0;
double   g_long_stop = 0;
double   g_short_stop = 0;
bool     g_buy_done = false;
bool     g_sell_done = false;
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
void RecomputeLevels()
{
   const double today_open = iOpen(_Symbol, InpDayTimeframe, 0);
   if(today_open == 0.0) return;
   g_today_open = today_open;
   g_range = LW_SelectVolatilityRange(_Symbol, InpDayTimeframe, InpVolatilityModel);
   if(g_range <= 0.0) return;

   g_buy_entry  = g_today_open + g_range * InpBuyMult;
   g_sell_entry = g_today_open - g_range * InpSellMult;
   g_long_stop  = g_buy_entry  - g_range * InpStopMult;
   g_short_stop = g_sell_entry + g_range * InpStopMult;
   g_buy_done   = false;
   g_sell_done  = false;
   g_prev_close = iClose(_Symbol, InpTriggerTimeframe, 1);
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
      ? entry + sl_distance * InpRewardValue
      : entry - sl_distance * InpRewardValue;
   const ENUM_ORDER_TYPE ot = (dir == LW_DIR_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   const double vol = ComputeVolume(ot, entry, sl);
   if(vol <= 0.0) return false;
   if(dir == LW_DIR_BUY) return g_trade.Buy (vol, _Symbol, entry, sl, tp, "LW vol breakout");
                          return g_trade.Sell(vol, _Symbol, entry, sl, tp, "LW vol breakout");
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(LW_IsNewBar(_Symbol, InpDayTimeframe, g_lastDay))
      RecomputeLevels();

   if(g_range <= 0.0) return;

   const double cur_close = iClose(_Symbol, InpTriggerTimeframe, 0);
   if(cur_close == 0.0) { g_prev_close = cur_close; return; }

   if(!g_buy_done
      && (InpDirection == LW_TRADE_BOTH || InpDirection == LW_TRADE_LONG_ONLY)
      && g_prev_close <= g_buy_entry && cur_close > g_buy_entry)
   {
      if(TryOpen(LW_DIR_BUY, SymbolInfoDouble(_Symbol, SYMBOL_ASK), g_long_stop))
         g_buy_done = true;
   }
   if(!g_sell_done
      && (InpDirection == LW_TRADE_BOTH || InpDirection == LW_TRADE_SHORT_ONLY)
      && g_prev_close >= g_sell_entry && cur_close < g_sell_entry)
   {
      if(TryOpen(LW_DIR_SELL, SymbolInfoDouble(_Symbol, SYMBOL_BID), g_short_stop))
         g_sell_done = true;
   }
   g_prev_close = cur_close;
}
//+------------------------------------------------------------------+
