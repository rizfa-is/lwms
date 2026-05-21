//+------------------------------------------------------------------+
//|                                       LWHiddenSmashDayEA.mq5     |
//|                                                       lwms       |
//|   Larry Williams Hidden Smash Day with context filters — Part 15  |
//|   (article 21393)                                                |
//+------------------------------------------------------------------+
//| Reads buy / sell hidden-smash arrows from LWHiddenSmashDay.ex5    |
//| and trades on confirmation. Stops at the smash bar's opposite    |
//| extreme by default; ATR-based stops are also available.          |
//+------------------------------------------------------------------+
#property copyright "lwms — Larry Williams port"
#property link      "https://github.com/rizfa-is/lwms"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <LWCommon.mqh>

#resource "\\Indicators\\lwms\\LWHiddenSmashDay.ex5"

input group "Information"
input ulong                  InpMagicNumber           = 254700980001;
input ENUM_TIMEFRAMES        InpTimeframe             = PERIOD_D1;

input group "Indicator inputs (must match LWHiddenSmashDay)"
input double                 InpQuartilePct           = LW_DEFAULT_QUARTILE_PCT;
input bool                   InpRequireCloseVsOpen    = false;

input group "Trade direction"
input ENUM_LW_TRADE_DIRECTION InpDirection            = LW_TRADE_BOTH;

input group "Stops & targets"
input ENUM_LW_SL_MODEL       InpStopModel             = LW_SL_STRUCTURE;
input int                    InpAtrPeriod             = LW_DEFAULT_ATR_PERIOD;
input double                 InpAtrMult               = LW_DEFAULT_ATR_MULT;
input double                 InpRiskRewardRatio       = LW_DEFAULT_RR;

input group "TradeDayFilter (Part 7)"
input bool                   InpUseTdwFilter          = false;
input bool                   InpAllowSunday           = false;
input bool                   InpAllowMonday           = true;
input bool                   InpAllowTuesday          = true;
input bool                   InpAllowWednesday        = true;
input bool                   InpAllowThursday         = true;
input bool                   InpAllowFriday           = true;
input bool                   InpAllowSaturday         = false;

input group "Sizing"
input ENUM_LW_SIZING_MODEL   InpSizingModel           = LW_SIZE_RISK_PCT;
input double                 InpRiskPerTradePct       = LW_DEFAULT_RISK_PCT;
input double                 InpFixedLot              = 0.10;
input double                 InpMaxLotSize            = 1.00;

CTrade   g_trade;
int      g_handle  = INVALID_HANDLE;
int      g_atrHandle = INVALID_HANDLE;
datetime g_lastBar = 0;

double buyArrow [];
double sellArrow[];

//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFilling(LW_DetectFillingMode(_Symbol));
   g_trade.SetDeviationInPoints(LW_DEFAULT_DEVIATION);

   g_handle = iCustom(_Symbol, InpTimeframe, "::Indicators\\lwms\\LWHiddenSmashDay.ex5",
                      InpQuartilePct, InpRequireCloseVsOpen, 1 /*HIDDEN_SMASH_CONFIRMED*/);
   if(g_handle == INVALID_HANDLE)
   {
      Print("Failed to load LWHiddenSmashDay: ", GetLastError());
      return INIT_FAILED;
   }
   if(InpStopModel == LW_SL_ATR)
   {
      g_atrHandle = iATR(_Symbol, InpTimeframe, InpAtrPeriod);
      if(g_atrHandle == INVALID_HANDLE)
      {
         Print("Failed to create ATR handle: ", GetLastError());
         return INIT_FAILED;
      }
   }
   ArraySetAsSeries(buyArrow,  true);
   ArraySetAsSeries(sellArrow, true);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_handle    != INVALID_HANDLE) IndicatorRelease(g_handle);
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
}

//+------------------------------------------------------------------+
LWTradeDayFilter BuildTdw()
{
   LWTradeDayFilter f;
   f.sun = InpAllowSunday;  f.mon = InpAllowMonday;
   f.tue = InpAllowTuesday; f.wed = InpAllowWednesday;
   f.thu = InpAllowThursday;f.fri = InpAllowFriday;
   f.sat = InpAllowSaturday;
   return f;
}

double LatestAtr()
{
   if(g_atrHandle == INVALID_HANDLE) return 0.0;
   double v[1];
   if(CopyBuffer(g_atrHandle, 0, 1, 1, v) <= 0) return 0.0;
   return v[0];
}

double ComputeVolume(const ENUM_ORDER_TYPE order_type,
                     const double entry, const double sl)
{
   if(InpSizingModel == LW_SIZE_MANUAL) return MathMin(InpFixedLot, InpMaxLotSize);
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
   const double tp = LW_TpFromRR(dir, entry, sl, InpRiskRewardRatio);
   const ENUM_ORDER_TYPE ot = (dir == LW_DIR_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   const double vol = ComputeVolume(ot, entry, sl);
   if(vol <= 0.0) return false;
   if(dir == LW_DIR_BUY) return g_trade.Buy (vol, _Symbol, entry, sl, tp, "LW hidden smash");
                          return g_trade.Sell(vol, _Symbol, entry, sl, tp, "LW hidden smash");
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!LW_IsNewBar(_Symbol, InpTimeframe, g_lastBar)) return;
   if(LW_HasOpenPositionByMagic(InpMagicNumber)) return;

   if(InpUseTdwFilter)
   {
      const LWTradeDayFilter tdw = BuildTdw();
      if(!LW_TradeDay_IsAllowed(tdw, TimeCurrent())) return;
   }

   if(CopyBuffer(g_handle, 0, 0, 10, buyArrow ) <= 0) return;
   if(CopyBuffer(g_handle, 1, 0, 10, sellArrow) <= 0) return;
   ArraySetAsSeries(buyArrow,  true);
   ArraySetAsSeries(sellArrow, true);

   // Most recent arrow is at index 2 (the smash bar; bar 1 is the confirmation).
   if((InpDirection == LW_TRADE_BOTH || InpDirection == LW_TRADE_LONG_ONLY)
      && buyArrow[2] != EMPTY_VALUE)
   {
      const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl;
      if(InpStopModel == LW_SL_ATR)
      {
         const double atr = LatestAtr();
         if(atr <= 0.0) return;
         sl = ask - atr * InpAtrMult;
      }
      else
      {
         sl = iLow(_Symbol, InpTimeframe, 2);   // smash bar's low
      }
      TryOpen(LW_DIR_BUY, ask, sl);
      return;
   }
   if((InpDirection == LW_TRADE_BOTH || InpDirection == LW_TRADE_SHORT_ONLY)
      && sellArrow[2] != EMPTY_VALUE)
   {
      const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl;
      if(InpStopModel == LW_SL_ATR)
      {
         const double atr = LatestAtr();
         if(atr <= 0.0) return;
         sl = bid + atr * InpAtrMult;
      }
      else
      {
         sl = iHigh(_Symbol, InpTimeframe, 2);
      }
      TryOpen(LW_DIR_SELL, bid, sl);
   }
}
//+------------------------------------------------------------------+
