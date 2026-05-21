//+------------------------------------------------------------------+
//|                                       LWSmashDayEA.mq5           |
//|                                                       lwms       |
//|     Larry Williams Smash Day with context filters — Part 12       |
//|     (article 21228)                                              |
//+------------------------------------------------------------------+
//| Reads buy / sell smash arrows from LWSmashDay.ex5 and trades on  |
//| confirmation. Adds three context layers from the article:        |
//|   - setup-validity countdown (drop setups not filled in N bars)  |
//|   - optional Trade-Day-of-Week filter                            |
//|   - optional setup-direction filter (buy / sell / both)          |
//+------------------------------------------------------------------+
#property copyright "lwms — Larry Williams port"
#property link      "https://github.com/rizfa-is/lwms"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <LWCommon.mqh>

#resource "\\Indicators\\lwms\\LWSmashDay.ex5"

input group "Information"
input ulong                  InpMagicNumber           = 254700970001;
input ENUM_TIMEFRAMES        InpTimeframe             = PERIOD_D1;

input group "Indicator inputs (must match LWSmashDay)"
input int                    InpBuyLookbackBars       = 1;
input int                    InpSellLookbackBars      = 1;
input int                    InpSetupValidityBars     = 3;

input group "Trade direction"
input ENUM_LW_TRADE_DIRECTION InpDirection            = LW_TRADE_BOTH;

input group "Stops & targets"
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
datetime g_lastBar = 0;

double buyArrow [];
double sellArrow[];

//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFilling(LW_DetectFillingMode(_Symbol));
   g_trade.SetDeviationInPoints(LW_DEFAULT_DEVIATION);

   g_handle = iCustom(_Symbol, InpTimeframe, "::Indicators\\lwms\\LWSmashDay.ex5",
                      InpBuyLookbackBars, InpSellLookbackBars);
   if(g_handle == INVALID_HANDLE)
   {
      Print("Failed to load LWSmashDay: ", GetLastError());
      return INIT_FAILED;
   }
   ArraySetAsSeries(buyArrow,  true);
   ArraySetAsSeries(sellArrow, true);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_handle != INVALID_HANDLE) IndicatorRelease(g_handle);
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
   if(dir == LW_DIR_BUY) return g_trade.Buy (vol, _Symbol, entry, sl, tp, "LW smash day");
                          return g_trade.Sell(vol, _Symbol, entry, sl, tp, "LW smash day");
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

   const int bars_to_copy = MathMax(InpSetupValidityBars + 4, 10);
   if(CopyBuffer(g_handle, 0, 0, bars_to_copy, buyArrow ) <= 0) return;
   if(CopyBuffer(g_handle, 1, 0, bars_to_copy, sellArrow) <= 0) return;
   ArraySetAsSeries(buyArrow,  true);
   ArraySetAsSeries(sellArrow, true);

   // Look for an active arrow within the validity window.
   for(int i = 1; i <= InpSetupValidityBars && i < ArraySize(buyArrow); i++)
   {
      if((InpDirection == LW_TRADE_BOTH || InpDirection == LW_TRADE_LONG_ONLY)
         && buyArrow[i] != EMPTY_VALUE)
      {
         const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         const double sl  = iLow(_Symbol, InpTimeframe, i);
         if(TryOpen(LW_DIR_BUY, ask, sl)) return;
      }
      if((InpDirection == LW_TRADE_BOTH || InpDirection == LW_TRADE_SHORT_ONLY)
         && sellArrow[i] != EMPTY_VALUE)
      {
         const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         const double sl  = iHigh(_Symbol, InpTimeframe, i);
         if(TryOpen(LW_DIR_SELL, bid, sl)) return;
      }
   }
}
//+------------------------------------------------------------------+
